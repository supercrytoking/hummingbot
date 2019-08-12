from .order_sizing_delegate cimport OrderSizingDelegate


cdef class InventorySkewMultipleSizeSizingDelegate(OrderSizingDelegate):
    cdef:
        double _order_step_size
        double _order_start_size
        int _number_of_orders
        double _inventory_target_base_percent
