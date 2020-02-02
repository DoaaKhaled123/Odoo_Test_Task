from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError


class StockRule(models.Model):
    _inherit = 'stock.rule'

    action = fields.Selection(selection_add=[('purchase_request', 'Purchase Request')])

    def _get_message_dict(self):
        message_dict = super(StockRule, self)._get_message_dict()
        dummy, destination, dummy = self._get_message_values()
        message_dict.update({
            'purchase_request': _(
                'When products are needed in <b>%s</b>, <br/> a Purchase Request is created to fulfill the need.') % (
                                    destination)
        })
        return message_dict

    @api.onchange('action')
    def _onchange_action(self):
        domain = {'picking_type_id': []}
        if self.action == 'purchase_request':
            self.location_src_id = False
            domain = {'picking_type_id': [('code', '=', 'incoming')]}
        return {'domain': domain}

    @api.multi
    def _run_buy(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        # res = super(StockRule, self)._run_buy(product_id, product_qty, product_uom, location_id, name, origin, values)
        cache2 = {}
        suppliers = product_id.seller_ids \
            .filtered(lambda r: (not r.company_id or r.company_id == values['company_id']) and (
            not r.product_id or r.product_id == product_id))
        if not suppliers:
            msg = _('There is no vendor associated to the product %s. Please define a vendor for this product.') % (
                product_id.display_name,)
            raise UserError(msg)
        supplier = self._make_po_select_supplier(values, suppliers)
        partner = supplier.name
        # we put `supplier_info` in values for extensibility purposes
        values['supplier'] = supplier
        # added by doaa
        domain2 = self._make_pr_get_domain(values, partner)
        if domain2 in cache2:
            pr = cache2[domain2]
        else:
            pr = self.env['sprogroup.purchase.request'].sudo().search([dom for dom in domain2])
            pr = pr[0] if pr else False
            cache2[domain2] = pr
        if not pr:
            vals = self._prepare_sprogroup_purchase_request(product_id, product_qty, product_uom, origin, values,
                                                            partner)
            company_id = values.get('company_id') and values['company_id'].id or self.env.user.company_id.id
            pr = self.env['sprogroup.purchase.request'].with_context(force_company=company_id).sudo().create(vals)
            cache2[domain2] = pr
        elif not pr.name or origin not in pr.name.split(', '):
            if pr.name:
                if origin:
                    pr.write({'name': pr.name + ', ' + origin})
                else:
                    pr.write({'name': pr.name})
            else:
                pr.write({'name': origin})

        # Create Line
        pr_line = False
        for line in pr.line_ids:
            if self.env.user.has_group('product.group_uom'):
                if line.product_id == product_id and line.product_uom_id == product_id.uom_po_id:
                    if line._merge_in_existing_line(product_id, product_qty, product_uom, location_id, name, origin,
                                                    values):
                        vals = self._update_sprogroup_purchase_request(product_id, product_qty, product_uom, values,
                                                                       line, partner)
                        pr_line = line.write(vals)
                        break
            else:
                if line.product_id == product_id:
                    if line._merge_in_existing_line(product_id, product_qty, product_uom, location_id, name, origin,
                                                    values):
                        vals = self._update_sprogroup_purchase_request(product_id, product_qty, product_uom, values,
                                                                       line, partner)
                        pr_line = line.write(vals)
                        break
        if not pr_line:
            vals = self._prepare_sprogroup_purchase_request_line(product_id, product_qty, product_uom, values, pr,
                                                                 partner)
            self.env['sprogroup.purchase.request.line'].sudo().create(vals)
            # return res

    def _update_sprogroup_purchase_request(self, product_id, product_qty, product_uom, values, line, partner):
        procurement_uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)

        return {
            'product_qty': line.product_qty + procurement_uom_po_qty,
        }

    @api.multi
    def _prepare_sprogroup_purchase_request_line(self, product_id, product_qty, product_uom, values, pr, partner):
        procurement_uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)

        product_lang = product_id.with_context({
            'lang': partner.lang,
            'partner_id': partner.id,
        })
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        date_required = self._get_sprogroup_purchase_request_line_date(values)

        return {
            'name': name,
            'product_qty': procurement_uom_po_qty,
            'product_id': product_id.id,
            'product_uom_id': product_id.uom_po_id.id,
            'date_required': date_required,
            'request_id': pr.id,
        }

    def _get_sprogroup_purchase_request_line_date(self, values):
        """Return the datetime value to use as date_required (``date_required``) for the
           sprogroup_purchase_request Lines created to satisfy the given procurement. """
        procurement_date_required = fields.Datetime.from_string(values['date_planned'])
        date_required = (procurement_date_required - relativedelta(days=values['company_id'].po_lead))
        return date_required

    def _get_sprogroup_purchase_request_start_date(self, product_id, product_qty, product_uom, values, partner,
                                                   date_start):
        """Return the datetime value to use as Order Date (``date_start``) for the
           purchase_request created to satisfy the given procurement. """
        seller = product_id._select_seller(
            partner_id=partner,
            quantity=product_qty,
            date=date_start and date_start.date(),
            uom_id=product_uom)

        return date_start - relativedelta(days=int(seller.delay))

    def _get_sprogroup_purchase_request_end_date(self, product_id, product_qty, product_uom, values, partner,
                                                 end_start):
        """Return the datetime value to use as Order Date (``end_start``) for the
           purchase_request created to satisfy the given procurement. """
        seller = product_id._select_seller(
            partner_id=partner,
            quantity=product_qty,
            date=end_start and end_start.date(),
            uom_id=product_uom)

        return end_start - relativedelta(days=int(seller.delay))

    def _prepare_sprogroup_purchase_request(self, product_id, product_qty, product_uom, origin, values, partner):
        schedule_date = self._get_sprogroup_purchase_request_line_date(values)
        purchase_date_start = self._get_sprogroup_purchase_request_start_date(product_id, product_qty, product_uom,
                                                                              values, partner, schedule_date)
        purchase_date_end = self._get_sprogroup_purchase_request_end_date(product_id, product_qty, product_uom, values,
                                                                          partner, schedule_date)
        fpos = self.env['account.fiscal.position'].with_context(
            force_company=values['company_id'].id).get_fiscal_position(partner.id)

        gpo = self.group_propagation_option
        group = (gpo == 'fixed' and self.group_id.id) or \
                (gpo == 'propagate' and values.get('group_id') and values['group_id'].id) or False

        return {
            'assigned_to': self.env.user.id,
            'requested_by': self.env.user.id,
            'name': origin,
            'date_start': purchase_date_start.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'end_start': purchase_date_end.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            # 'group_id': group

        }

    def _make_pr_get_domain(self, values, partner):
        domain = ()
        gpo = self.group_propagation_option
        group = (gpo == 'fixed' and self.group_id) or \
                (gpo == 'propagate' and 'group_id' in values and values['group_id']) or False

        domain += (
            ('assigned_to', '=', self.env.user.id),
            ('state', '=', 'draft'),
        )
        if group:
            domain += (('group_id', '=', group.id),)
        return domain
