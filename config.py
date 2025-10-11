# -*- coding: utf-8 -*-
"""
Central configuration for the inventory management system.
"""

# Pagination settings
PAGINATION_SETTINGS = {
    'INVENTORY_PER_PAGE': 20,      # Items per page for inventory lists
    'MOVEMENTS_PER_PAGE': 20,      # Items per page for movement history
    'DISPOSALS_PER_PAGE': 20,      # Items per page for disposal records
    'EDIT_ITEMS_PER_PAGE': 20,     # Items per page for edit items view
    'DELETE_ITEMS_PER_PAGE': 20,   # Items per page for delete items view
    'DEFAULT_PER_PAGE': 20,        # Default items per page for general pagination
}

# You can easily modify these values in one place to affect all pagination
# For example, to show 20 items per page instead of 10, change any of the values above