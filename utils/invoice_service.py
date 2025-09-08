# utils/invoice_service.py

from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
from .invoice_data import get_payment_terms

logger = logging.getLogger(__name__)

class InvoiceService:
    """Service class for invoice business logic"""
    
    @staticmethod
    def calculate_due_date(invoice_date: datetime, payment_term_days: int = 30) -> datetime:
        """Calculate due date based on payment terms"""
        return invoice_date + timedelta(days=payment_term_days)
    
    @staticmethod
    def group_ans_by_vendor(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Group ANs by vendor for invoice creation"""
        grouped = {}
        for vendor_code, group in df.groupby('vendor_code'):
            grouped[vendor_code] = group.copy()
        return grouped
    
    @staticmethod
    def calculate_invoice_totals(df: pd.DataFrame) -> Dict:
        """Calculate invoice totals from selected ANs (without VAT details)"""
        totals = {
            'total_quantity': df['uninvoiced_quantity'].sum(),
            'total_lines': len(df),
            'po_count': df['po_number'].nunique(),
            'an_count': df['arrival_note_number'].nunique()
        }
        
        # Calculate total value (handle currency in string format)
        total_value = 0
        currency = None
        
        for _, row in df.iterrows():
            # Extract value and currency from "123.45 USD" format
            cost_parts = str(row['buying_unit_cost']).split()
            if len(cost_parts) >= 2:
                unit_cost = float(cost_parts[0])
                if not currency:
                    currency = cost_parts[1]
                
                total_value += unit_cost * row['uninvoiced_quantity']
        
        totals['total_value'] = round(total_value, 2)
        totals['currency'] = currency or 'USD'
        
        return totals
    
    @staticmethod
    def calculate_invoice_totals_with_vat(df: pd.DataFrame) -> Dict:
        """Calculate invoice totals including VAT breakdown"""
        totals = {
            'total_quantity': df['uninvoiced_quantity'].sum(),
            'total_lines': len(df),
            'po_count': df['po_number'].nunique(),
            'an_count': df['arrival_note_number'].nunique()
        }
        
        # Calculate subtotal and VAT
        subtotal = 0
        total_vat = 0
        currency = None
        
        for _, row in df.iterrows():
            # Extract value and currency from "123.45 USD" format
            cost_parts = str(row['buying_unit_cost']).split()
            if len(cost_parts) >= 2:
                unit_cost = float(cost_parts[0])
                if not currency:
                    currency = cost_parts[1]
                
                line_amount = unit_cost * row['uninvoiced_quantity']
                subtotal += line_amount
                
                # Calculate VAT for this line
                vat_percent = row.get('vat_percent', 0)
                vat_amount = line_amount * vat_percent / 100
                total_vat += vat_amount
        
        totals['subtotal'] = round(subtotal, 2)
        totals['total_vat'] = round(total_vat, 2)
        totals['total_value'] = round(subtotal + total_vat, 2)
        totals['currency'] = currency or 'USD'
        
        return totals
    
    @staticmethod
    def prepare_invoice_summary(df: pd.DataFrame) -> pd.DataFrame:
        """Prepare summary for invoice preview"""
        # Group by PO, product, and VAT rate
        summary = df.groupby(['po_number', 'pt_code', 'product_name', 'buying_unit_cost', 'vat_percent']).agg({
            'uninvoiced_quantity': 'sum',
            'arrival_note_number': lambda x: ', '.join(x.unique())
        }).reset_index()
        
        # Calculate line amount without VAT
        summary['line_amount'] = summary.apply(
            lambda row: float(str(row['buying_unit_cost']).split()[0]) * row['uninvoiced_quantity'], 
            axis=1
        )
        
        # Calculate VAT amount for each line
        summary['vat_amount'] = summary['line_amount'] * summary['vat_percent'] / 100
        
        # Calculate total with VAT
        summary['total_amount'] = summary['line_amount'] + summary['vat_amount']
        
        # Format VAT percentage
        summary['vat_display'] = summary['vat_percent'].apply(lambda x: f"{x:.0f}%")
        
        # Format monetary values
        summary['line_amount'] = summary['line_amount'].apply(lambda x: f"{x:,.2f}")
        summary['vat_amount'] = summary['vat_amount'].apply(lambda x: f"{x:,.2f}")
        summary['total_amount'] = summary['total_amount'].apply(lambda x: f"{x:,.2f}")
        
        # Rename columns for display
        summary.columns = ['PO Number', 'PT Code', 'Product', 'Unit Cost', 'VAT %', 
                          'Quantity', 'AN Numbers', 'Subtotal', 'VAT Amount', 'Total', 'VAT Display']
        
        # Reorder columns for better display
        return summary[['PO Number', 'PT Code', 'Product', 'Unit Cost', 
                       'Quantity', 'AN Numbers', 'Subtotal', 'VAT Display', 
                       'VAT Amount', 'Total']]
    
    @staticmethod
    def validate_invoice_data(invoice_data: Dict) -> Tuple[bool, str]:
        """Validate invoice data before creation"""
        required_fields = [
            'invoice_number', 'invoiced_date', 'due_date',
            'seller_id', 'buyer_id', 'currency_id'
        ]
        
        for field in required_fields:
            if field not in invoice_data or not invoice_data[field]:
                return False, f"Missing required field: {field}"
        
        # Validate dates
        if invoice_data['due_date'] < invoice_data['invoiced_date']:
            return False, "Due date cannot be before invoice date"
        
        # Validate amount
        if invoice_data.get('total_invoiced_amount', 0) <= 0:
            return False, "Invoice amount must be greater than 0"
        
        return True, ""
    
    @staticmethod
    def format_invoice_display(row: pd.Series) -> Dict:
        """Format invoice data for display"""
        return {
            'Invoice #': row.get('invoice_number', ''),
            'Date': row.get('invoiced_date', '').strftime('%Y-%m-%d') if pd.notna(row.get('invoiced_date')) else '',
            'Vendor': row.get('vendor', ''),
            'Amount': f"{row.get('total_invoiced_amount', 0):,.2f} {row.get('currency', '')}",
            'Payment Term': row.get('payment_term', 'N/A'),
            'Lines': row.get('line_count', 0),
            'POs': row.get('po_count', 0),
            'Created': row.get('created_date', '').strftime('%Y-%m-%d %H:%M') if pd.notna(row.get('created_date')) else ''
        }
    
    @staticmethod
    def get_payment_terms_dict() -> Dict:
        """Get available payment terms as dictionary"""
        try:
            df = get_payment_terms()
            # Convert to dictionary with ID as key
            return {
                row['id']: {
                    'name': row['name'],
                    'days': row['days'],
                    'description': row.get('description', '')
                }
                for _, row in df.iterrows()
            }
        except Exception as e:
            logger.error(f"Error getting payment terms dict: {e}")
            # Return default if error
            return {
                1: {'name': 'Net 30', 'days': 30, 'description': 'Payment due in 30 days'},
                2: {'name': 'Net 60', 'days': 60, 'description': 'Payment due in 60 days'},
                3: {'name': 'Net 90', 'days': 90, 'description': 'Payment due in 90 days'},
                4: {'name': 'COD', 'days': 0, 'description': 'Cash on delivery'},
                5: {'name': 'Net 45', 'days': 45, 'description': 'Payment due in 45 days'}
            }
    
    @staticmethod
    def can_lines_be_invoiced_together(df: pd.DataFrame) -> Tuple[bool, str]:
        """Check if selected CAN lines can be invoiced together"""
        # Check same vendor
        vendors = df['vendor_code'].unique()
        if len(vendors) > 1:
            return False, "Multiple vendors selected. Each invoice must be for a single vendor."
        
        # Check same currency
        currencies = df['buying_unit_cost'].apply(lambda x: x.split()[-1] if isinstance(x, str) else '').unique()
        currencies = [c for c in currencies if c]  # Remove empty
        if len(currencies) > 1:
            return False, f"Multiple currencies found: {', '.join(currencies)}. All items must have same currency."
        
        # Check same entity
        entities = df['legal_entity_code'].unique()
        if len(entities) > 1:
            return False, "Multiple legal entities selected. Each invoice must be for a single entity."
        
        # Check payment terms consistency - now more lenient
        # Only show warning if different payment terms, not block
        payment_terms = df['payment_term'].dropna().unique()
        if len(payment_terms) > 1:
            # This is now just a warning, not a blocking error
            logger.warning(f"Multiple payment terms found: {', '.join(payment_terms)}")
        
        return True, ""
    
    @staticmethod
    def determine_payment_term(selected_df: pd.DataFrame, details_df: pd.DataFrame) -> Tuple[int, str, int]:
        """
        Determine which payment term to use for the invoice
        Returns: (payment_term_id, payment_term_name, payment_days)
        """
        # Get payment terms from selected data
        payment_terms = selected_df['payment_term'].dropna()
        
        if not payment_terms.empty:
            # Use the most common payment term
            most_common_term = payment_terms.mode()[0]
            
            # Get the corresponding ID and days from details
            matching_rows = details_df[details_df['payment_term'] == most_common_term]
            if not matching_rows.empty:
                payment_term_info = matching_rows.iloc[0]
                return (
                    int(payment_term_info['payment_term_id']),
                    most_common_term,
                    int(payment_term_info.get('payment_term_days', 30))
                )
        
        # Try to get from details_df if available
        if not details_df.empty and 'payment_term_id' in details_df.columns:
            first_row = details_df.iloc[0]
            payment_term_id = int(first_row['payment_term_id']) if pd.notna(first_row['payment_term_id']) else 1
            payment_term_name = first_row.get('payment_term_name', first_row.get('payment_term', 'Net 30'))
            payment_days = int(first_row.get('payment_term_days', 30))
            
            return (payment_term_id, payment_term_name, payment_days)
        
        # Default to Net 30
        return (1, 'Net 30', 30)