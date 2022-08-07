from odoo import fields, models, api

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