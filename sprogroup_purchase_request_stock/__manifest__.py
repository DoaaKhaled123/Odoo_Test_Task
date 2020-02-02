# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sprogroup Purchase Request Stock',
    'version': '1.0',
    'category': 'Purchases',
    'author': 'Doaa Khaled',
    'description': """
         Use Purchase Request Stock module for create purchase request with product Reordering Rule.
    """,
    'summary': 'Create purchase order',
    'data': [],
    'depends': ['base', 'purchase', 'sprogroup_purchase_request', 'product', 'purchase_stock', 'stock'],
    'data': [
        'views/product_template_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
