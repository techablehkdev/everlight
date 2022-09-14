import json
from odoo import models, api

class AccountMoveLine(models.Model):
    
    _inherit = 'account.move.line'
                        
    @api.onchange('quantity', 'discount', 'price_unit', 'tax_ids', 'x_studio_weight', 'x_studio_price')
    def _onchange_price_subtotal(self):
        for line in self:
            if not line.move_id.is_invoice(include_receipts=True):
                continue
            line.update({ 'price_unit':  (self.x_studio_price*self.x_studio_weight)/self.quantity})
            line.update(line._get_price_total_and_subtotal())
            line.update(line._get_fields_onchange_subtotal())
            
    def _get_price_total_and_subtotal(self, price_unit=None, quantity=None, discount=None, currency=None, product=None, partner=None, taxes=None, move_type=None):
        self.ensure_one()
        return self._get_price_total_and_subtotal_model(
            price_unit=(self.x_studio_price*self.x_studio_weight/self.quantity) if price_unit is None else price_unit,
            quantity=self.quantity if quantity is None else quantity,
            discount=self.discount if discount is None else discount,
            currency=self.currency_id if currency is None else currency,
            product=self.product_id if product is None else product,
            partner=self.partner_id if partner is None else partner,
            taxes=self.tax_ids if taxes is None else taxes,
            move_type=self.move_id.move_type if move_type is None else move_type,
        )