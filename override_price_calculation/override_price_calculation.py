from odoo import models, api

# _logger = logging.getLogger(__name__)


class Override_Price_Calculation(models.Model):
    
    _inherit = 'sale.order.line'

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'x_studio_weight')
    def _compute_amount(self):
        res = super(Override_Price_Calculation, self)._compute_amount()
        for line in self:
#           price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            price = line.price_unit * line.x_studio_weight * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
            if self.env.context.get('import_file', False) and not self.env.user.user_has_groups('account.group_account_manager'):
                line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])
        return res


    _inherit = 'account.move'

    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type, x_studio_weight):

        res = super(Override_Price_Calculation, self)._get_price_total_and_subtotal_model()
        
        line_discount_price_unit = price_unit * (1 - (discount / 100.0))
        subtotal = x_studio_weight * line_discount_price_unit
        
        if taxes:
            taxes_res = taxes._origin.with_context(force_sign=1).compute_all(line_discount_price_unit,
                quantity=x_studio_weight, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
            res['price_subtotal'] = taxes_res['total_excluded']
            res['price_total'] = taxes_res['total_included']
        else:
            res['price_total'] = res['price_subtotal'] = subtotal
        #In case of multi currency, round before it's use for computing debit credit
        if currency:
            res = {k: currency.round(v) for k, v in res.items()}
        return res