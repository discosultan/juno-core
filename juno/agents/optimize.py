import asyncio
import logging
import math
from decimal import Decimal
from functools import partial
from random import Random
from typing import Any, Dict, List, Optional, Tuple, Type

from deap import algorithms, base, creator, tools

from juno.math import floor_multiple
from juno.solvers import Python, Solver
from juno.strategies import Strategy, get_strategy_type
from juno.time import time_ms
from juno.typing import get_input_type_hints
from juno.utils import get_args_by_params

from . import Agent

_log = logging.getLogger(__name__)


class Optimize(Agent):
    def __init__(self, solver: Solver, validating_solver: Python) -> None:
        super().__init__()
        self.solver = solver
        self.validating_solver = validating_solver

    async def run(
        self,
        exchange: str,
        symbol: str,
        interval: int,
        start: int,
        quote: Decimal,
        strategy: str,
        end: Optional[int] = None,
        restart_on_missed_candle: bool = False,
        population_size: int = 50,
        max_generations: int = 1000,
        mutation_probability: Decimal = Decimal('0.2'),
        seed: Optional[int] = None,
    ) -> None:
        now = time_ms()

        if end is None:
            end = floor_multiple(now, interval)

        assert end <= now
        assert end > start
        assert quote > 0

        # It's useful to set a seed for idempotent results. Helpful for debugging.
        if seed is not None:
            _log.info(f'seeding randomizer ({seed})')
        random = Random(seed)

        strategy_type = get_strategy_type(strategy)

        # Objectives:
        #   - max total profit
        #   - min mean drawdown
        #   - min max drawdown
        #   - max mean position profit
        #   - min mean position duration
        weights = (1.0, -1.0, -1.0, 1.0, -1.0)
        creator.create('FitnessMulti', base.Fitness, weights=weights)
        creator.create('Individual', list, fitness=creator.FitnessMulti)

        toolbox = base.Toolbox()

        # Initialization.
        meta = strategy_type.meta()
        attrs = [partial(c.random, random) for c in meta.params.values()]

        # TODO: Fix!!!!!!!
        def generate_random_strategy_args() -> List[Any]:
            while True:
                # TODO: We should only regen attrs for ones failing constraint test.
                args = [a() for a in attrs]
                for names, constraint in meta.constraints.items():
                    if not constraint(*get_args_by_params(meta.params.keys(), args, names)):
                        continue
                break
            return args

        toolbox.register('strategy_args', generate_random_strategy_args)
        toolbox.register(
            'individual', tools.initIterate, creator.Individual, toolbox.strategy_args
        )
        toolbox.register('population', tools.initRepeat, list, toolbox.individual)

        # Operators.

        def mut_individual(individual: list, indpb: float) -> Tuple[list]:
            for i, attr in enumerate(attrs):
                if random.random() < indpb:
                    individual[i] = attr()
            return individual,

        def cx_individual(ind1: list, ind2: list) -> Tuple[list, list]:
            end = len(ind1) - 1

            # Variant A.
            cxpoint1, cxpoint2 = 0, -1
            while cxpoint2 < cxpoint1:
                cxpoint1 = random.randint(0, end)
                cxpoint2 = random.randint(0, end)

            # Variant B.
            # cxpoint1 = random.randint(0, end)
            # cxpoint2 = random.randint(cxpoint1, end)

            cxpoint2 += 1

            ind1[cxpoint1:cxpoint2], ind2[cxpoint1:cxpoint2] = ind2[cxpoint1:cxpoint2
                                                                    ], ind1[cxpoint1:cxpoint2]

            return ind1, ind2

        # eta - Crowding degree of the crossover. A high eta will produce children resembling to
        # their parents, while a small eta will produce solutions much more different.

        # toolbox.register('mate', tools.tools.cxSimulatedBinaryBounded, low=BOUND_LOW,
        #                  up=BOUND_UP, eta=20.0)
        toolbox.register('mate', cx_individual)
        # toolbox.register('mutate', tools.mutPolynomialBounded, low=BOUND_LOW, up=BOUND_UP,
        #                  eta=20.0, indpb=1.0 / NDIM)
        toolbox.register('mutate', mut_individual, indpb=1.0 / len(attrs))
        toolbox.register('select', tools.selNSGA2)
        solve = await self.solver.get(
            strategy_type=strategy_type,
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            start=start,
            end=end,
            quote=quote
        )
        toolbox.register('evaluate', solve)

        toolbox.population_size = population_size
        toolbox.max_generations = max_generations
        toolbox.mutation_probability = mutation_probability

        _log.info('evolving')

        pop = toolbox.population(n=toolbox.population_size)
        pop = toolbox.select(pop, len(pop))

        hall = tools.HallOfFame(1)

        # Returns the final population and logbook with the statistics of the evolution.
        final_pop, stat = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: algorithms.eaMuPlusLambda(
                pop,
                toolbox,
                mu=toolbox.population_size,
                lambda_=toolbox.population_size,
                cxpb=Decimal(1) - toolbox.mutation_probability,
                mutpb=toolbox.mutation_probability,
                stats=None,
                ngen=toolbox.max_generations,
                halloffame=hall,
                verbose=False
            )
        )

        best_args = hall[0]
        best_result = solve(best_args)
        _log.info(f'final backtest result: {best_result}')
        self.result = _output_as_strategy_args(strategy_type, best_args)

        # In case of using other than python solver, run the backtest with final args also with
        # Python solver to assert the equality of results.
        if self.solver != self.validating_solver:
            solver_name = type(self.solver).__name__.lower()
            _log.info(f'validating {solver_name} solver result with best '
                      'args against python solver')
            validation_solve = await self.validating_solver.get(
                strategy_type=strategy_type,
                exchange=exchange,
                symbol=symbol,
                interval=interval,
                start=start,
                end=end,
                quote=quote
            )
            validation_result = validation_solve(best_args)
            if not _isclose(validation_result, best_result):
                raise Exception(
                    f'Optimizer results differ for input {self.result} between python and '
                    f'{solver_name} solvers:\n{validation_result}\n{best_result}'
                )


def _output_as_strategy_args(
    strategy_type: Type[Strategy], best_args: List[Any]
) -> Dict[str, Any]:
    strategy_config = {'name': strategy_type.__name__.lower()}
    for key, value in zip(get_input_type_hints(strategy_type.__init__).keys(), best_args):
        strategy_config[key] = value
    return strategy_config


def _isclose(a: Tuple[Decimal, ...], b: Tuple[Decimal, ...]) -> bool:
    isclose = True
    for i in range(0, len(a)):
        isclose = isclose and math.isclose(a[i], b[i], rel_tol=Decimal('1e-14'))
    return isclose
