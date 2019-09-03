import math
import unittest

from hummingbot.client.performance_analysis import PerformanceAnalysis
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion


class TestPerformanceAnalysis(unittest.TestCase):

    def setUp(self) -> None:
        self._weth_price = 1.0
        self._eth_price = 1.0
        self._dai_price = 0.95
        self._usdc_price = 1.05
        self._price = 50
        ExchangeRateConversion.set_global_exchange_rate_config({
            "conversion_required": {
                "WETH": {"default": self._weth_price, "source": "None"},
                "ETH": {"default": self._eth_price, "source": "None"},
                "DAI": {"default": self._dai_price, "source": "None"},
                "USDC": {"default": self._usdc_price, "source": "None"},
                "USD": {"default": 1.0, "source": "None"}
            }
        })

    def test_basic_one_ex(self):
        """ Test performance analysis on a one exchange balance. """
        performance_analysis = PerformanceAnalysis()
        starting_weth = 0.5
        starting_dai = 60
        current_weth = 0.4
        current_dai = 70

        performance_analysis.add_balances("WETH", starting_weth, True, True)
        performance_analysis.add_balances("DAI", starting_dai, False, True)
        performance_analysis.add_balances("WETH", current_weth, True, False)
        performance_analysis.add_balances("DAI", current_dai, False, False)

        calculated_starting_token, calculated_starting_amount = performance_analysis.compute_starting(self._price)
        calculated_current_token, calculated_current_amount = performance_analysis.compute_current(self._price)
        calculated_delta_token, calculated_delta_amount = performance_analysis.compute_delta(self._price)
        calculated_return = performance_analysis.compute_return(self._price)

        expected_starting_amount = (starting_weth * self._price) + starting_dai
        expected_current_amount = (current_weth * self._price) + current_dai
        expected_delta_amount = expected_current_amount - expected_starting_amount
        expected_return = ((expected_current_amount / expected_starting_amount) - 1) * 100

        self.assertEqual(calculated_starting_token, "DAI",
                         msg="Basic one exchange test: expected starting token incorrectly determined.")
        self.assertAlmostEquals(calculated_starting_amount, expected_starting_amount,
                                msg="Basic one exchange test: expected starting amount incorrectly determined.")
        self.assertEqual(calculated_current_token, "DAI",
                         msg="Basic one exchange test: expected current token incorrectly determined.")
        self.assertAlmostEquals(calculated_current_amount, expected_current_amount,
                                msg="Basic one exchange test: expected current amount incorrectly determined.")
        self.assertEqual(calculated_delta_token, "DAI",
                         msg="Basic one exchange test: expected delta token incorrectly determined.")
        self.assertAlmostEquals(calculated_delta_amount, expected_delta_amount,
                                msg="Basic one exchange test: expected delta amount incorrectly determined.")
        self.assertAlmostEquals(calculated_return, expected_return,
                                msg="Basic one exchange test: return incorrectly determined.")

    def test_basic_two_ex(self):
        """ Test performance analysis on a two exchange balance with the same currencies trading in both exchanges. """
        performance_analysis = PerformanceAnalysis()
        starting_weth_1 = 0.5
        starting_dai_1 = 60
        starting_weth_2 = 0.7
        starting_dai_2 = 50
        current_weth_1 = 0.4
        current_dai_1 = 70
        current_weth_2 = 0.3
        current_dai_2 = 70

        performance_analysis.add_balances("WETH", starting_weth_1, True, True)
        performance_analysis.add_balances("DAI", starting_dai_1, False, True)
        performance_analysis.add_balances("WETH", starting_weth_2, True, True)
        performance_analysis.add_balances("DAI", starting_dai_2, False, True)
        performance_analysis.add_balances("WETH", current_weth_1, True, False)
        performance_analysis.add_balances("DAI", current_dai_1, False, False)
        performance_analysis.add_balances("WETH", current_weth_2, True, False)
        performance_analysis.add_balances("DAI", current_dai_2, False, False)

        calculated_starting_token, calculated_starting_amount = performance_analysis.compute_starting(self._price)
        calculated_current_token, calculated_current_amount = performance_analysis.compute_current(self._price)
        calculated_delta_token, calculated_delta_amount = performance_analysis.compute_delta(self._price)
        calculated_return = performance_analysis.compute_return(self._price)

        starting_weth = starting_weth_1 + starting_weth_2
        starting_dai = starting_dai_1 + starting_dai_2
        current_weth = current_weth_1 + current_weth_2
        current_dai = current_dai_1 + current_dai_2

        expected_starting_amount = (starting_weth * self._price) + starting_dai
        expected_current_amount = (current_weth * self._price) + current_dai
        expected_delta_amount = expected_current_amount - expected_starting_amount
        expected_return = ((expected_current_amount / expected_starting_amount) - 1) * 100

        self.assertEqual(calculated_starting_token, "DAI",
                         msg="Basic two exchange test: expected starting token incorrectly determined.")
        self.assertAlmostEquals(calculated_starting_amount, expected_starting_amount,
                                msg="Basic two exchange test: expected starting amount incorrectly determined.")
        self.assertEqual(calculated_current_token, "DAI",
                         msg="Basic two exchange test: expected current token incorrectly determined.")
        self.assertAlmostEquals(calculated_current_amount, expected_current_amount,
                                msg="Basic two exchange test: expected current amount incorrectly determined.")
        self.assertEqual(calculated_delta_token, "DAI",
                         msg="Basic two exchange test: expected delta token incorrectly determined.")
        self.assertAlmostEquals(calculated_delta_amount, expected_delta_amount,
                                msg="Basic two exchange test: expected delta amount incorrectly determined.")
        self.assertAlmostEquals(calculated_return, expected_return,
                                msg="Basic two exchange test: return incorrectly determined.")

    def test_different_tokens_two_ex(self):
        """ Test performance analysis on a two exchange balance with different currencies trading. Note that this test
        will not work as the config file that contains the conversion has not been loaded."""
        performance_analysis = PerformanceAnalysis()
        starting_weth_1 = 0.5
        starting_dai_1 = 60
        starting_eth_2 = 0.7
        starting_usdc_2 = 50
        current_weth_1 = 0.4
        current_dai_1 = 70
        current_eth_2 = 0.3
        current_usdc_2 = 70

        performance_analysis.add_balances("WETH", starting_weth_1, True, True)
        performance_analysis.add_balances("DAI", starting_dai_1, False, True)
        performance_analysis.add_balances("ETH", starting_eth_2, True, True)
        performance_analysis.add_balances("USDC", starting_usdc_2, False, True)
        performance_analysis.add_balances("WETH", current_weth_1, True, False)
        performance_analysis.add_balances("DAI", current_dai_1, False, False)
        performance_analysis.add_balances("ETH", current_eth_2, True, False)
        performance_analysis.add_balances("USDC", current_usdc_2, False, False)

        calculated_starting_token, calculated_starting_amount = performance_analysis.compute_starting(self._price)
        calculated_current_token, calculated_current_amount = performance_analysis.compute_current(self._price)
        calculated_delta_token, calculated_delta_amount = performance_analysis.compute_delta(self._price)
        calculated_return = performance_analysis.compute_return(self._price)

        starting_weth = starting_weth_1 + starting_eth_2
        starting_dai = starting_dai_1 + (starting_usdc_2 * self._usdc_price * (1 / self._dai_price))
        current_weth = current_weth_1 + current_eth_2
        current_dai = current_dai_1 + (current_usdc_2 * self._usdc_price * (1 / self._dai_price))

        expected_starting_amount = (starting_weth * self._price) + starting_dai
        expected_current_amount = (current_weth * self._price) + current_dai
        expected_delta_amount = expected_current_amount - expected_starting_amount
        expected_return = ((expected_current_amount / expected_starting_amount) - 1) * 100

        self.assertEqual(calculated_starting_token, "DAI",
                         msg="Two exchange test w/ diff tokens: expected starting token incorrectly determined.")
        self.assertAlmostEquals(calculated_starting_amount, expected_starting_amount,
                                msg="Two exchange test w/ diff tokens: "
                                    "expected starting amount incorrectly determined.")
        self.assertEqual(calculated_current_token, "DAI",
                         msg="Two exchange test w/ diff tokens: expected current token incorrectly determined.")
        self.assertAlmostEquals(calculated_current_amount, expected_current_amount,
                                msg="Two exchange test w/ diff tokens: expected current amount incorrectly determined.")
        self.assertEqual(calculated_delta_token, "DAI",
                         msg="Two exchange test w/ diff tokens: expected delta token incorrectly determined.")
        self.assertAlmostEquals(calculated_delta_amount, expected_delta_amount,
                                msg="Two exchange test w/ diff tokens: expected delta amount incorrectly determined.")
        self.assertAlmostEquals(calculated_return, expected_return,
                                msg="Two exchange test w/ diff tokens: return incorrectly determined.")

    def test_nan_starting(self):
        """ Test the case where the starting balance is 0. """
        performance_analysis = PerformanceAnalysis()
        starting_weth = 0
        starting_dai = 0
        current_weth = 0.3
        current_dai = 70

        performance_analysis.add_balances("WETH", starting_weth, True, True)
        performance_analysis.add_balances("DAI", starting_dai, False, True)
        performance_analysis.add_balances("WETH", current_weth, True, False)
        performance_analysis.add_balances("DAI", current_dai, False, False)

        calculated_starting_token, calculated_starting_amount = performance_analysis.compute_starting(self._price)
        calculated_current_token, calculated_current_amount = performance_analysis.compute_current(self._price)
        calculated_delta_token, calculated_delta_amount = performance_analysis.compute_delta(self._price)
        calculated_return = performance_analysis.compute_return(self._price)

        expected_starting_amount = (starting_weth * self._price) + starting_dai
        expected_current_amount = (current_weth * self._price) + current_dai
        expected_delta_amount = expected_current_amount - expected_starting_amount

        self.assertEqual(calculated_starting_token, "DAI",
                         msg="Starting value of 0 test: expected starting token incorrectly determined.")
        self.assertAlmostEquals(calculated_starting_amount, expected_starting_amount,
                                msg="Starting value of 0 test: expected starting amount incorrectly determined.")
        self.assertEqual(calculated_current_token, "DAI",
                         msg="Starting value of 0 test: expected current token incorrectly determined.")
        self.assertAlmostEquals(calculated_current_amount, expected_current_amount,
                                msg="Starting value of 0 test: expected current amount incorrectly determined.")
        self.assertEqual(calculated_delta_token, "DAI",
                         msg="Starting value of 0 test: expected delta token incorrectly determined.")
        self.assertAlmostEquals(calculated_delta_amount, expected_delta_amount,
                                msg="Starting value of 0 test: expected delta amount incorrectly determined.")
        self.assertTrue(math.isnan(calculated_return), "Starting value of 0 test: return incorrectly determined.")


if __name__ == "__main__":
    unittest.main()
