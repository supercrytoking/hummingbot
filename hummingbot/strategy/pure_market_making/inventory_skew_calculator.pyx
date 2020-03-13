import numpy as np

from .data_types import InventorySkewBidAskRatios


def calculate_bid_ask_ratios_from_base_asset_ratio(
        base_asset_amount: float, quote_asset_amount: float, price: float,
        target_base_asset_ratio: float, base_asset_range: float) -> InventorySkewBidAskRatios:
    return c_calculate_bid_ask_ratios_from_base_asset_ratio(base_asset_amount,
                                                            quote_asset_amount,
                                                            price,
                                                            target_base_asset_ratio,
                                                            base_asset_range)


cdef object c_calculate_bid_ask_ratios_from_base_asset_ratio(
        double base_asset_amount, double quote_asset_amount, double price,
        double target_base_asset_ratio, double base_asset_range):
    cdef:
        double total_portfolio_value = base_asset_amount * price + quote_asset_amount

    if total_portfolio_value <= 0.0 or base_asset_range <= 0.0:
        return InventorySkewBidAskRatios(0.0, 0.0)

    cdef:
        double base_asset_value = base_asset_amount * price
        double target_base_asset_value = total_portfolio_value * target_base_asset_ratio
        double left_base_asset_value_limit = max(target_base_asset_value - base_asset_range * price, 0.0)
        double right_base_asset_value_limit = target_base_asset_value + base_asset_range * price
        double left_inventory_ratio = np.interp(base_asset_value,
                                                [left_base_asset_value_limit, target_base_asset_value],
                                                [0.0, 0.5])
        double right_inventory_ratio = np.interp(base_asset_value,
                                                 [target_base_asset_value, right_base_asset_value_limit],
                                                 [0.5, 1.0])
        double bid_adjustment = (np.interp(left_inventory_ratio, [0, 0.5], [2.0, 1.0])
                                 if base_asset_value < target_base_asset_value
                                 else np.interp(right_inventory_ratio, [0.5, 1], [1.0, 0.0]))
        double ask_adjustment = 2.0 - bid_adjustment

    return InventorySkewBidAskRatios(bid_adjustment, ask_adjustment)
