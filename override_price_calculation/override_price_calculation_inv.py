import json
from odoo import models, api

class AccountMoveLine(models.Model):
    
    _inherit = 'account.move.line'

    @api.onchange('x_studio_price', 'x_studio_weight', 'quantity')
    def _onchange_update_price_unit(self):
        for line in self:
            if not line.move_id.is_invoice(include_receipts=True):
                continue
            if (self.x_studio_price*self.x_studio_weight /self.quantity) != False:
                line.update({ 'price_unit':  self.x_studio_price*self.x_studio_weight/self.quantity})
            else:
                line.update({ 'price_unit':  0})
                
    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id or line.display_type in ('line_section', 'line_note'):
                continue

            line.name = line._get_computed_name()
            line.account_id = line._get_computed_account()
            taxes = line._get_computed_taxes()
            if taxes and line.move_id.fiscal_position_id:
                taxes = line.move_id.fiscal_position_id.map_tax(taxes)
            line.tax_ids = taxes
            line.product_uom_id = line._get_computed_uom()
            line.price_unit = line._get_computed_price_unit()
            line.x_studio_price = line._get_computed_price_unit()
            
class SaleOrderLine(models.Model):
    
    _inherit = 'sale.order.line'

    @api.depends('x_studio_price', 'x_studio_weight', 'product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.x_studio_price * self.x_studio_weight  * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
            if self.env.context.get('import_file', False) and not self.env.user.user_has_groups('account.group_account_manager'):
                line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])
            if self.product_uom_qty !=False:
                if (self.x_studio_price*self.x_studio_weight /self.product_uom_qty) != False:
                    line.update({ 'price_unit':  self.x_studio_price*self.x_studio_weight/self.product_uom_qty})
                    
                    
    def _update_taxes(self):
        if not self.product_id:
            return

        vals = {}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
            vals['product_uom_qty'] = self.product_uom_qty or 1.0

        product = self.product_id.with_context(
            partner=self.order_id.partner_id,
            quantity=vals.get('product_uom_qty') or self.product_uom_qty,
            date=self.order_id.date_order,
            pricelist=self.order_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        self._compute_tax_id()

        if self.order_id.pricelist_id and self.order_id.partner_id:
            vals['price_unit'] = product._get_tax_included_unit_price(
                self.company_id,
                self.order_id.currency_id,
                self.order_id.date_order,
                'sale',
                fiscal_position=self.order_id.fiscal_position_id,
                product_price_unit=self._get_display_price(product),
                product_currency=self.order_id.currency_id
            )
            vals['x_studio_price'] = product._get_tax_included_unit_price(
                self.company_id,
                self.order_id.currency_id,
                self.order_id.date_order,
                'sale',
                fiscal_position=self.order_id.fiscal_position_id,
                product_price_unit=self._get_display_price(product),
                product_currency=self.order_id.currency_id
            )

        self.update(vals)