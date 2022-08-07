from odoo import models, api

class Override_Price_Calculation_Inv(models.Model):
    
    _inherit = 'account.move'

    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, discount, currency, product, partner, taxes, move_type, x_studio_weight):

        res = super(Override_Price_Calculation_Inv, self)._get_price_total_and_subtotal_model()
        

        quantity = x_studio_weight
        line_discount_price_unit = price_unit * (1 - (discount / 100.0))
        subtotal = quantity * line_discount_price_unit
        
        if taxes:
            taxes_res = taxes._origin.with_context(force_sign=1).compute_all(line_discount_price_unit,
                quantity=quantity, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
            res['price_subtotal'] = taxes_res['total_excluded']
            res['price_total'] = taxes_res['total_included']
        else:
            res['price_total'] = res['price_subtotal'] = subtotal
        #In case of multi currency, round before it's use for computing debit credit
        if currency:
            res = {k: currency.round(v) for k, v in res.items()}
        return res