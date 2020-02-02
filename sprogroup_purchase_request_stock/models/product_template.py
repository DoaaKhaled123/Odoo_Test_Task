from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.addons import decimal_precision as dp
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    purchase_request = fields.Boolean(string="Create Purchase Request", copy=False)


# class ProductProduct(models.Model):
#     _inherit = 'product.product'
#
#     purchase_request = fields.Boolean(string="Create Purchase Request", copy=False)
