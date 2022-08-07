import json
from odoo import models, api

class Override_Price_Calculation_Inv(models.Model):
    
    _inherit = 'account.move.line'
        
    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
#         res = super(Override_Price_Calculation_Inv, self)._get_price_total_and_subtotal_model()
        ''' This method is used to compute 'price_total' & 'price_subtotal'.

        :param price_unit:  The current price unit.
        :param quantity:    The current quantity.
        :param discount:    The current discount.
        :param currency:    The line's currency.
        :param product:     The line's product.
        :param partner:     The line's partner.
        :param taxes:       The applied taxes.
        :param move_type:   The type of the move.
        :return:            A dictionary containing 'price_subtotal' & 'price_total'.
        '''
        res = {}

        # Compute 'price_subtotal'.
        line_discount_price_unit = price_unit * (1 - (discount / 100.0))
        subtotal = self.x_studio_weight * line_discount_price_unit

        # Compute 'price_total'.
        if taxes:
            taxes_res = taxes._origin.with_context(force_sign=1).compute_all(line_discount_price_unit,
                quantity=self.x_studio_weight, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
            res['price_subtotal'] = taxes_res['total_excluded']
            res['price_total'] = taxes_res['total_included']
        else:
            res['price_total'] = res['price_subtotal'] = subtotal
        #In case of multi currency, round before it's use for computing debit credit
        if currency:
            res = {k: currency.round(v) for k, v in res.items()}
        return res


class Override_Tax_Calculation_Inv(models.Model):
    _inherit = 'account.move'
        
    def _recompute_tax_lines(self, recompute_tax_base_amount=False, tax_rep_lines_to_recompute=None):
            """ Compute the dynamic tax lines of the journal entry.

            :param recompute_tax_base_amount: Flag forcing only the recomputation of the `tax_base_amount` field.
            """
            self.ensure_one()
            in_draft_mode = self != self._origin

            def _serialize_tax_grouping_key(grouping_dict):
                ''' Serialize the dictionary values to be used in the taxes_map.
                :param grouping_dict: The values returned by '_get_tax_grouping_key_from_tax_line' or '_get_tax_grouping_key_from_base_line'.
                :return: A string representing the values.
                '''
                return '-'.join(str(v) for v in grouping_dict.values())

            def _compute_base_line_taxes(base_line):
                ''' Compute taxes amounts both in company currency / foreign currency as the ratio between
                amount_currency & balance could not be the same as the expected currency rate.
                The 'amount_currency' value will be set on compute_all(...)['taxes'] in multi-currency.
                :param base_line:   The account.move.line owning the taxes.
                :return:            The result of the compute_all method.
                '''
                move = base_line.move_id

                if move.is_invoice(include_receipts=True):
                    handle_price_include = True
                    sign = -1 if move.is_inbound() else 1
                    quantity = base_line.x_studio_weight
                    is_refund = move.move_type in ('out_refund', 'in_refund')
                    price_unit_wo_discount = sign * base_line.price_unit * (1 - (base_line.discount / 100.0))
                else:
                    handle_price_include = False
                    quantity = 1.0
                    tax_type = base_line.tax_ids[0].type_tax_use if base_line.tax_ids else None
                    is_refund = (tax_type == 'sale' and base_line.debit) or (tax_type == 'purchase' and base_line.credit)
                    price_unit_wo_discount = base_line.amount_currency

                return base_line.tax_ids._origin.with_context(force_sign=move._get_tax_force_sign()).compute_all(
                    price_unit_wo_discount,
                    currency=base_line.currency_id,
                    quantity=quantity,
                    product=base_line.product_id,
                    partner=base_line.partner_id,
                    is_refund=is_refund,
                    handle_price_include=handle_price_include,
                    include_caba_tags=move.always_tax_exigible,
                )

            taxes_map = {}

            # ==== Add tax lines ====
            to_remove = self.env['account.move.line']
            for line in self.line_ids.filtered('tax_repartition_line_id'):
                grouping_dict = self._get_tax_grouping_key_from_tax_line(line)
                grouping_key = _serialize_tax_grouping_key(grouping_dict)
                if grouping_key in taxes_map:
                    # A line with the same key does already exist, we only need one
                    # to modify it; we have to drop this one.
                    to_remove += line
                else:
                    taxes_map[grouping_key] = {
                        'tax_line': line,
                        'amount': 0.0,
                        'tax_base_amount': 0.0,
                        'grouping_dict': False,
                    }
            if not recompute_tax_base_amount:
                self.line_ids -= to_remove

            # ==== Mount base lines ====
            for line in self.line_ids.filtered(lambda line: not line.tax_repartition_line_id):
                # Don't call compute_all if there is no tax.
                if not line.tax_ids:
                    if not recompute_tax_base_amount:
                        line.tax_tag_ids = [(5, 0, 0)]
                    continue

                compute_all_vals = _compute_base_line_taxes(line)

                # Assign tags on base line
                if not recompute_tax_base_amount:
                    line.tax_tag_ids = compute_all_vals['base_tags'] or [(5, 0, 0)]

                for tax_vals in compute_all_vals['taxes']:
                    grouping_dict = self._get_tax_grouping_key_from_base_line(line, tax_vals)
                    grouping_key = _serialize_tax_grouping_key(grouping_dict)

                    tax_repartition_line = self.env['account.tax.repartition.line'].browse(tax_vals['tax_repartition_line_id'])
                    tax = tax_repartition_line.invoice_tax_id or tax_repartition_line.refund_tax_id

                    taxes_map_entry = taxes_map.setdefault(grouping_key, {
                        'tax_line': None,
                        'amount': 0.0,
                        'tax_base_amount': 0.0,
                        'grouping_dict': False,
                    })
                    taxes_map_entry['amount'] += tax_vals['amount']
                    taxes_map_entry['tax_base_amount'] += self._get_base_amount_to_display(tax_vals['base'], tax_repartition_line, tax_vals['group'])
                    taxes_map_entry['grouping_dict'] = grouping_dict

            # ==== Pre-process taxes_map ====
            taxes_map = self._preprocess_taxes_map(taxes_map)

            # ==== Process taxes_map ====
            for taxes_map_entry in taxes_map.values():
                # The tax line is no longer used in any base lines, drop it.
                if taxes_map_entry['tax_line'] and not taxes_map_entry['grouping_dict']:
                    if not recompute_tax_base_amount:
                        self.line_ids -= taxes_map_entry['tax_line']
                    continue

                currency = self.env['res.currency'].browse(taxes_map_entry['grouping_dict']['currency_id'])

                # Don't create tax lines with zero balance.
                if currency.is_zero(taxes_map_entry['amount']):
                    if taxes_map_entry['tax_line'] and not recompute_tax_base_amount:
                        self.line_ids -= taxes_map_entry['tax_line']
                    continue

                # tax_base_amount field is expressed using the company currency.
                tax_base_amount = currency._convert(taxes_map_entry['tax_base_amount'], self.company_currency_id, self.company_id, self.date or fields.Date.context_today(self))

                # Recompute only the tax_base_amount.
                if recompute_tax_base_amount:
                    if taxes_map_entry['tax_line']:
                        taxes_map_entry['tax_line'].tax_base_amount = tax_base_amount
                    continue

                balance = currency._convert(
                    taxes_map_entry['amount'],
                    self.company_currency_id,
                    self.company_id,
                    self.date or fields.Date.context_today(self),
                )
                to_write_on_line = {
                    'amount_currency': taxes_map_entry['amount'],
                    'currency_id': taxes_map_entry['grouping_dict']['currency_id'],
                    'debit': balance > 0.0 and balance or 0.0,
                    'credit': balance < 0.0 and -balance or 0.0,
                    'tax_base_amount': tax_base_amount,
                }

                if taxes_map_entry['tax_line']:
                    # Update an existing tax line.
                    if tax_rep_lines_to_recompute and taxes_map_entry['tax_line'].tax_repartition_line_id not in tax_rep_lines_to_recompute:
                        continue

                    taxes_map_entry['tax_line'].update(to_write_on_line)
                else:
                    # Create a new tax line.
                    create_method = in_draft_mode and self.env['account.move.line'].new or self.env['account.move.line'].create
                    tax_repartition_line_id = taxes_map_entry['grouping_dict']['tax_repartition_line_id']
                    tax_repartition_line = self.env['account.tax.repartition.line'].browse(tax_repartition_line_id)

                    if tax_rep_lines_to_recompute and tax_repartition_line not in tax_rep_lines_to_recompute:
                        continue

                    tax = tax_repartition_line.invoice_tax_id or tax_repartition_line.refund_tax_id
                    taxes_map_entry['tax_line'] = create_method({
                        **to_write_on_line,
                        'name': tax.name,
                        'move_id': self.id,
                        'company_id': self.company_id.id,
                        'company_currency_id': self.company_currency_id.id,
                        'tax_base_amount': tax_base_amount,
                        'exclude_from_invoice_tab': True,
                        **taxes_map_entry['grouping_dict'],
                    })

                if in_draft_mode:
                    taxes_map_entry['tax_line'].update(taxes_map_entry['tax_line']._get_fields_onchange_balance(force_computation=True))