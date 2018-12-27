from decimal import Decimal

import pytest

from juno.indicators import Sma, Ema, Dema, Cci, DM, DI, DX, Adx, Adxr, Macd, Stoch, Rsi


def test_adx():
    inputs = [
        [  # High.
            94.1875, 94.5000, 93.5000, 92.7500, 92.8750, 90.7500, 89.8750, 89.1250, 90.4375,
            90.0000, 88.5000, 87.7500, 87.0625, 85.8125, 86.5625, 90.3750, 91.3750, 92.2500,
            93.3750, 92.0625, 92.8750, 93.9375, 95.2500, 97.1250, 97.1875, 94.8750, 94.3125,
            93.3125, 94.1250, 96.9375, 101.125, 108.750, 115.000, 117.125, 115.000, 116.625,
            118.000, 119.250, 119.250, 118.812, 118.375, 119.938, 117.750, 118.625, 117.125,
            116.375, 113.875, 112.250, 113.688, 114.250
        ],
        [  # Low.
            92.1250, 91.9375, 91.5000, 90.3125, 90.5000, 84.3750, 86.4375, 86.4375, 88.2500,
            87.0625, 86.9375, 85.8750, 85.0000, 84.5000, 84.3750, 88.4375, 88.3750, 89.5000,
            91.0000, 89.5000, 89.5625, 90.8750, 92.8750, 95.7344, 94.7500, 92.8750, 91.6875,
            91.4375, 92.2500, 92.7500, 95.3125, 98.5000, 108.938, 113.625, 111.188, 110.625,
            115.125, 116.750, 116.125, 117.062, 116.812, 117.125, 116.250, 112.000, 112.250,
            109.375, 108.375, 107.312, 111.375, 108.688
        ],
        [  # Close.
            92.3750, 92.5625, 92.0000, 91.7500, 91.5625, 89.9375, 88.8750, 87.1250, 89.6250,
            89.1875, 87.0000, 87.3125, 85.0000, 84.9375, 86.0000, 89.8125, 89.6250, 91.6875,
            91.1250, 90.1875, 91.0469, 93.1875, 94.8125, 96.1250, 95.4375, 93.0000, 91.7500,
            92.7500, 93.8750, 96.6250, 98.6875, 108.438, 113.688, 115.250, 112.750, 115.875,
            117.562, 117.438, 119.125, 117.500, 117.938, 117.625, 116.750, 116.562, 112.625,
            113.812, 110.000, 111.438, 112.250, 109.375
        ]
    ]
    # Value 29.5118 was corrected to 29.5117.
    outputs = [[18.4798, 17.7329, 16.6402, 16.4608, 17.5570, 19.9758, 22.9245, 25.8535, 27.6536,
                29.5117, 31.3907, 33.2726, 34.7625, 36.1460, 37.3151, 38.6246, 39.4151, 38.3660,
                37.3919, 35.4565, 33.3321, 31.0167, 29.3056, 27.5566]]
    _assert(Adx(14), inputs, outputs, 4)


def test_adxr():
    inputs = [
        [  # High.
            94.1875, 94.5000, 93.5000, 92.7500, 92.8750, 90.7500, 89.8750, 89.1250, 90.4375,
            90.0000, 88.5000, 87.7500, 87.0625, 85.8125, 86.5625, 90.3750, 91.3750, 92.2500,
            93.3750, 92.0625, 92.8750, 93.9375, 95.2500, 97.1250, 97.1875, 94.8750, 94.3125,
            93.3125, 94.1250, 96.9375, 101.125, 108.750, 115.000, 117.125, 115.000, 116.625,
            118.000, 119.250, 119.250, 118.812, 118.375, 119.938, 117.750, 118.625, 117.125,
            116.375, 113.875, 112.250, 113.688, 114.250
        ],
        [  # Low.
            92.1250, 91.9375, 91.5000, 90.3125, 90.5000, 84.3750, 86.4375, 86.4375, 88.2500,
            87.0625, 86.9375, 85.8750, 85.0000, 84.5000, 84.3750, 88.4375, 88.3750, 89.5000,
            91.0000, 89.5000, 89.5625, 90.8750, 92.8750, 95.7344, 94.7500, 92.8750, 91.6875,
            91.4375, 92.2500, 92.7500, 95.3125, 98.5000, 108.938, 113.625, 111.188, 110.625,
            115.125, 116.750, 116.125, 117.062, 116.812, 117.125, 116.250, 112.000, 112.250,
            109.375, 108.375, 107.312, 111.375, 108.688
        ],
        [  # Close.
            92.3750, 92.5625, 92.0000, 91.7500, 91.5625, 89.9375, 88.8750, 87.1250, 89.6250,
            89.1875, 87.0000, 87.3125, 85.0000, 84.9375, 86.0000, 89.8125, 89.6250, 91.6875,
            91.1250, 90.1875, 91.0469, 93.1875, 94.8125, 96.1250, 95.4375, 93.0000, 91.7500,
            92.7500, 93.8750, 96.6250, 98.6875, 108.438, 113.688, 115.250, 112.750, 115.875,
            117.562, 117.438, 119.125, 117.500, 117.938, 117.625, 116.750, 116.562, 112.625,
            113.812, 110.000, 111.438, 112.250, 109.375
        ]
    ]
    outputs = [[27.3129, 27.5240, 27.6324, 27.9379, 27.9615, 28.6838, 29.1905, 29.5928, 29.3351,
                29.4087, 29.4736]]
    _assert(Adxr(14), inputs, outputs, 4)


def test_cci():
    inputs = [
        [  # High.
            15.1250, 15.0520, 14.8173, 14.6900, 14.7967, 14.7940, 14.0930, 14.7000, 14.5255,
            14.6579, 14.7842, 14.8273
        ],
        [  # Low.
            14.9360, 14.6267, 14.5557, 14.4600, 14.5483, 13.9347, 13.8223, 14.0200, 14.2652,
            14.3773, 14.5527, 14.3309
        ],
        [  # Close.
            14.9360, 14.7520, 14.5857, 14.6000, 14.6983, 13.9460, 13.9827, 14.4500, 14.3452,
            14.4197, 14.5727, 14.4773
        ]
    ]
    outputs = [[18.0890, 84.4605, 109.1186, 46.6540]]
    _assert(Cci(5), inputs, outputs, 4)


def test_dema():
    inputs = [[
        122.906, 126.500, 140.406, 174.000, 159.812, 170.000, 176.750, 175.531, 166.562, 163.750,
        170.500, 175.000, 184.750, 202.781
    ]]
    outputs = [[172.0780, 168.5718, 170.2278, 173.4940, 180.5297, 194.1428]]
    _assert(Dema(5), inputs, outputs, 4)


def test_di():
    inputs = [
        [  # High.
            94.1875, 94.5000, 93.5000, 92.7500, 92.8750, 90.7500, 89.8750, 89.1250, 90.4375,
            90.0000, 88.5000, 87.7500, 87.0625, 85.8125, 86.5625, 90.3750, 91.3750, 92.2500,
            93.3750, 92.0625, 92.8750, 93.9375, 95.2500, 97.1250, 97.1875, 94.8750, 94.3125,
            93.3125, 94.1250, 96.9375, 101.125, 108.750, 115.000, 117.125, 115.000, 116.625,
            118.000, 119.250, 119.250, 118.812, 118.375, 119.938, 117.750, 118.625, 117.125,
            116.375, 113.875, 112.250, 113.688, 114.250
        ],
        [  # Low.
            92.1250, 91.9375, 91.5000, 90.3125, 90.5000, 84.3750, 86.4375, 86.4375, 88.2500,
            87.0625, 86.9375, 85.8750, 85.0000, 84.5000, 84.3750, 88.4375, 88.3750, 89.5000,
            91.0000, 89.5000, 89.5625, 90.8750, 92.8750, 95.7344, 94.7500, 92.8750, 91.6875,
            91.4375, 92.2500, 92.7500, 95.3125, 98.5000, 108.938, 113.625, 111.188, 110.625,
            115.125, 116.750, 116.125, 117.062, 116.812, 117.125, 116.250, 112.000, 112.250,
            109.375, 108.375, 107.312, 111.375, 108.688
        ],
        [  # Close.
            92.3750, 92.5625, 92.0000, 91.7500, 91.5625, 89.9375, 88.8750, 87.1250, 89.6250,
            89.1875, 87.0000, 87.3125, 85.0000, 84.9375, 86.0000, 89.8125, 89.6250, 91.6875,
            91.1250, 90.1875, 91.0469, 93.1875, 94.8125, 96.1250, 95.4375, 93.0000, 91.7500,
            92.7500, 93.8750, 96.6250, 98.6875, 108.438, 113.688, 115.250, 112.750, 115.875,
            117.562, 117.438, 119.125, 117.500, 117.938, 117.625, 116.750, 116.562, 112.625,
            113.812, 110.000, 111.438, 112.250, 109.375
        ]
    ]
    outputs = [
        [
            04.7619, 06.5404, 15.7975, 17.1685, 18.2181, 20.0392, 18.6830, 19.1863, 20.4108,
            22.5670, 26.1316, 24.4414, 22.7738, 21.1796, 20.0974, 21.3093, 26.4203, 32.9361,
            41.7807, 48.6368, 49.4654, 45.5589, 43.4969, 43.7326, 44.0367, 41.3368, 39.6102,
            38.3048, 39.3410, 38.0298, 32.8260, 29.6147, 25.7233, 23.1495, 21.1075, 22.8568,
            20.5857
        ],
        [
            31.2925, 29.4074, 26.0300, 23.9950, 22.2758, 20.8841, 23.4324, 21.4148, 19.7238,
            18.5036, 17.3764, 18.8646, 22.5699, 24.1567, 23.6037, 22.3726, 19.8789, 17.0398,
            13.4042, 11.6853, 10.8837, 14.7622, 13.1147, 12.4005, 11.7988, 12.3016, 11.7878,
            11.9265, 11.2104, 12.7810, 19.8102, 17.8722, 20.9206, 20.6465, 20.7242, 19.8413,
            22.6700
        ]
    ]
    _assert(DI(14), inputs, outputs, 4)


def test_dm():
    inputs = [
        [  # High.
            94.1875, 94.5000, 93.5000, 92.7500, 92.8750, 90.7500, 89.8750, 89.1250, 90.4375,
            90.0000, 88.5000, 87.7500, 87.0625, 85.8125, 86.5625, 90.3750, 91.3750, 92.2500,
            93.3750, 92.0625, 92.8750, 93.9375, 95.2500, 97.1250, 97.1875, 94.8750, 94.3125,
            93.3125, 94.1250, 96.9375, 101.125, 108.750, 115.000, 117.125, 115.000, 116.625,
            118.000, 119.250, 119.250, 118.812, 118.375, 119.938, 117.750, 118.625, 117.125,
            116.375, 113.875, 112.250, 113.688, 114.250
        ],
        [  # Low.
            92.1250, 91.9375, 91.5000, 90.3125, 90.5000, 84.3750, 86.4375, 86.4375, 88.2500,
            87.0625, 86.9375, 85.8750, 85.0000, 84.5000, 84.3750, 88.4375, 88.3750, 89.5000,
            91.0000, 89.5000, 89.5625, 90.8750, 92.8750, 95.7344, 94.7500, 92.8750, 91.6875,
            91.4375, 92.2500, 92.7500, 95.3125, 98.5000, 108.938, 113.625, 111.188, 110.625,
            115.125, 116.750, 116.125, 117.062, 116.812, 117.125, 116.250, 112.000, 112.250,
            109.375, 108.375, 107.312, 111.375, 108.688
        ]
    ]
    outputs = [
        [
            01.7500, 02.3750, 06.0179, 06.5880, 06.9924, 07.6180, 07.0738, 07.3811, 07.9163,
            08.6634, 09.9196, 09.2110, 08.5531, 07.9422, 07.3749, 07.6606, 09.9259, 13.4044,
            20.0720, 24.8882, 25.2355, 23.4330, 23.3842, 23.0889, 22.6897, 21.0690, 19.5641,
            18.1666, 18.4320, 17.1154, 15.8929, 14.7577, 13.7036, 12.7248, 11.8158, 12.4099,
            11.5234
        ],
        [
            11.5000, 10.6786, 09.9158, 09.2075, 08.5499, 07.9392, 08.8721, 08.2384, 07.6499,
            07.1035, 06.5961, 07.1093, 08.4765, 09.0586, 08.6615, 08.0428, 07.4684, 06.9349,
            06.4395, 05.9796, 05.5525, 07.5929, 07.0505, 06.5469, 06.0793, 06.2700, 05.8222,
            05.6563, 05.2523, 05.7521, 09.5913, 08.9062, 11.1450, 11.3489, 11.6013, 10.7726,
            12.6902
        ]
    ]
    _assert(DM(14), inputs, outputs, 4)


def test_dx():
    inputs = [
        [  # High.
            94.1875, 94.5000, 93.5000, 92.7500, 92.8750, 90.7500, 89.8750, 89.1250, 90.4375,
            90.0000, 88.5000, 87.7500, 87.0625, 85.8125, 86.5625, 90.3750, 91.3750, 92.2500,
            93.3750, 92.0625, 92.8750, 93.9375, 95.2500, 97.1250, 97.1875, 94.8750, 94.3125,
            93.3125, 94.1250, 96.9375, 101.125, 108.750, 115.000, 117.125, 115.000, 116.625,
            118.000, 119.250, 119.250, 118.812, 118.375, 119.938, 117.750, 118.625, 117.125,
            116.375, 113.875, 112.250, 113.688, 114.250
        ],
        [  # Low.
            92.1250, 91.9375, 91.5000, 90.3125, 90.5000, 84.3750, 86.4375, 86.4375, 88.2500,
            87.0625, 86.9375, 85.8750, 85.0000, 84.5000, 84.3750, 88.4375, 88.3750, 89.5000,
            91.0000, 89.5000, 89.5625, 90.8750, 92.8750, 95.7344, 94.7500, 92.8750, 91.6875,
            91.4375, 92.2500, 92.7500, 95.3125, 98.5000, 108.938, 113.625, 111.188, 110.625,
            115.125, 116.750, 116.125, 117.062, 116.812, 117.125, 116.250, 112.000, 112.250,
            109.375, 108.375, 107.312, 111.375, 108.688
        ],
        [  # Close.
            92.3750, 92.5625, 92.0000, 91.7500, 91.5625, 89.9375, 88.8750, 87.1250, 89.6250,
            89.1875, 87.0000, 87.3125, 85.0000, 84.9375, 86.0000, 89.8125, 89.6250, 91.6875,
            91.1250, 90.1875, 91.0469, 93.1875, 94.8125, 96.1250, 95.4375, 93.0000, 91.7500,
            92.7500, 93.8750, 96.6250, 98.6875, 108.438, 113.688, 115.250, 112.750, 115.875,
            117.562, 117.438, 119.125, 117.500, 117.938, 117.625, 116.750, 116.562, 112.625,
            113.812, 110.000, 111.438, 112.250, 109.375
        ]
    ]
    # Value 73.5850 was corrected to 73.5849.
    outputs = [[
        73.5849, 63.6115, 24.4637, 16.5840, 10.0206, 02.0645, 11.2771, 05.4886, 01.7117,
        09.8936, 20.1233, 12.8777, 00.4497, 06.5667, 08.0233, 02.4342, 14.1285, 31.8079,
        51.4207, 61.2569, 63.9309, 51.0546, 53.6679, 55.8176, 57.7373, 54.1312, 54.1312,
        52.5138, 55.6475, 49.6919, 24.7277, 24.7277, 10.2966, 05.7150, 00.9162, 07.0623,
        04.8185
    ]]
    _assert(DX(14), inputs, outputs, 4)


def test_ema():
    inputs = [[25.000, 24.875, 24.781, 24.594, 24.500, 24.625, 25.219, 27.250]]
    outputs = [[25.000, 24.958, 24.899, 24.797, 24.698, 24.674, 24.856, 25.654]]
    _assert(Ema(5), inputs, outputs, 3)


def test_sma():
    inputs = [[25.000, 24.875, 24.781, 24.594, 24.500, 24.625, 25.219, 27.250]]
    outputs = [[24.750, 24.675, 24.744, 25.238]]
    _assert(Sma(5), inputs, outputs, 3)


def test_macd():
    inputs = [[
        63.750, 63.625, 63.000, 62.750, 63.250, 65.375, 66.000, 65.000, 64.875, 64.750, 64.375,
        64.375, 64.625, 64.375, 64.500, 65.250, 67.875, 68.000, 66.875, 66.250, 65.875, 66.000,
        65.875, 64.750, 63.000, 63.375, 63.375, 63.375, 63.875, 65.500, 63.250, 60.750, 57.250,
        59.125, 59.250, 58.500, 59.125, 59.750, 60.625, 60.500, 59.000, 59.500, 58.875, 59.625,
        59.875, 59.750, 59.625, 59.250, 58.875, 59.125, 60.875, 60.750, 61.125, 62.500, 63.250
    ]]
    outputs = [
        [  # MACD.
            +0.069246173, -0.056749361, -0.155174919, -0.193316296, -0.099255145, -0.192932945,
            -0.451916620, -0.912958472, -1.124556845, -1.268899802, -1.424364329, -1.483699214,
            -1.466784652, -1.371359250, -1.290278236, -1.324512659, -1.299028706, -1.311252875,
            -1.249862534, -1.168783424, -1.101261161, -1.045157593, -1.017413140, -1.012278166,
            -0.978102663, -0.808978519, -0.676278653, -0.536210248, -0.316924099, -0.084694969
        ],
        [  # Signal.
            +0.069246173, +0.044047066, +0.004202669, -0.035301124, -0.048091928, -0.077060132,
            -0.152031429, -0.304216838, -0.468284839, -0.628407832, -0.787599131, -0.926819148,
            -1.034812249, -1.102121649, -1.139752966, -1.176704905, -1.201169665, -1.223186307,
            -1.228521552, -1.216573927, -1.193511374, -1.163840617, -1.134555122, -1.110099731,
            -1.083700317, -1.028755957, -0.958260496, -0.873850447, -0.762465177, -0.626911135
        ],
        [  # Divergence.
            +0.000000000, -0.100796427, -0.159377588, -0.158015172, -0.051163217, -0.115872813,
            -0.299885190, -0.608741634, -0.656272006, -0.640491970, -0.636765198, -0.556880067,
            -0.431972403, -0.269237601, -0.150525270, -0.147807754, -0.097859041, -0.088066568,
            -0.021340981, +0.047790503, +0.092250213, +0.118683025, +0.117141982, +0.097821565,
            +0.105597654, +0.219777438, +0.281981844, +0.337640199, +0.445541078, +0.542216167
        ]
    ]
    _assert(Macd(12, 26, 9), inputs, outputs, 9)


def test_rsi():
    inputs = [[
        37.8750, 39.5000, 38.7500, 39.8125, 40.0000, 39.8750, 40.1875, 41.2500, 41.1250,
        41.6250, 41.2500, 40.1875, 39.9375, 39.9375, 40.5000, 41.9375, 42.2500, 42.2500,
        41.8750, 41.8750
    ]]
    outputs = [[
        76.6667, 78.8679, 84.9158, 81.4863, 84.5968, 73.0851, 49.3173, 45.0119, 45.0119,
        57.9252, 75.9596, 78.4676, 78.4676, 65.6299, 65.6299
    ]]
    _assert(Rsi(5), inputs, outputs, 4)


def test_stoch():
    inputs = [
        [  # High.
            34.3750, 34.7500, 34.2188, 33.8281, 33.4375, 33.4688, 34.3750, 34.7188, 34.6250,
            34.9219, 34.9531, 35.0625, 34.7812, 34.3438, 34.5938, 34.3125, 34.2500, 34.1875,
            33.7812, 33.8125, 33.9688, 33.8750, 34.0156, 33.5312
        ],
        [  # Low.
            33.5312, 33.9062, 33.6875, 33.2500, 33.0000, 32.9375, 33.2500, 34.0469, 33.9375,
            34.0625, 34.4375, 34.5938, 33.7656, 33.2188, 33.9062, 32.6562, 32.7500, 33.1562,
            32.8594, 33.0000, 33.2969, 33.2812, 33.0312, 33.0156
        ],
        [  # Close.
            34.3125, 34.1250, 33.7500, 33.6406, 33.0156, 33.0469, 34.2969, 34.1406, 34.5469,
            34.3281, 34.8281, 34.8750, 33.7812, 34.2031, 34.4844, 32.6719, 34.0938, 33.2969,
            33.0625, 33.7969, 33.3281, 33.8750, 33.1094, 33.1875
        ]
    ]
    outputs = [
        [  # K.
            84.1524, 75.9890, 84.3623, 82.0235, 59.0655, 45.9745, 41.0782, 40.8947, 45.6496,
            33.7903, 40.5626, 40.9688, 42.7932, 61.2935, 45.5442, 38.8516
        ],
        [  # D.
            58.0105, 72.0631, 81.5012, 80.7916, 75.1504, 62.3545, 48.7061, 42.6491, 42.5409,
            40.1115, 40.0008, 38.4405, 41.4415, 48.3518, 49.8770, 48.5631
        ]
    ]
    _assert(Stoch(5, 3, 3), inputs, outputs, 4)


def _assert(indicator, inputs, outputs, precision):
    input_len, output_len = len(inputs[0]), len(outputs[0])
    offset = input_len - output_len
    for i in range(0, input_len):
        result = indicator.update(*(Decimal(input[i]) for input in inputs))
        if i >= offset:
            if not isinstance(result, tuple):
                result = result,
            for j in range(0, len(result)):
                assert pytest.approx(
                    float(result[j]), abs=10**-precision) == outputs[j][i - offset]
