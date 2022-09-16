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