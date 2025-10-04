# pages/2_📊_Invoice_History.py

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import io

# Import utils
from utils.auth import AuthManager
from utils.invoice_data import get_recent_invoices
from utils.invoice_service import InvoiceService

# Page config
st.set_page_config(
    page_title="Invoice History",
    page_icon="📊",
    layout="wide"
)

# Initialize
auth = AuthManager()
auth.require_auth()
service = InvoiceService()

def main():
    st.title("📊 Purchase Invoice History")
    
    # Filters
    with st.expander("🔍 Search Filters", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date_filter = st.selectbox(
                "Date Range",
                ["Last 7 days", "Last 30 days", "Last 90 days", "This Month", "All Time", "Custom"],
                key="date_filter"
            )
            
            if date_filter == "Custom":
                date_from = st.date_input("From Date", key="custom_from")
                date_to = st.date_input("To Date", key="custom_to")
        
        with col2:
            invoice_search = st.text_input(
                "Invoice Number",
                placeholder="Search invoice number...",
                key="invoice_search"
            )
            
            vendor_search = st.text_input(
                "Vendor",
                placeholder="Search vendor...",
                key="vendor_search"
            )
        
        with col3:
            # Invoice Type filter
            invoice_type_filter = st.selectbox(
                "Invoice Type",
                ["All", "Commercial Invoice (CI)", "Advance Payment (PI)"],
                key="invoice_type_filter"
            )
            
            limit = st.number_input(
                "Max Records",
                min_value=10,
                max_value=500,
                value=100,
                step=50,
                key="record_limit"
            )
    
    # Get data
    df = get_recent_invoices(limit=int(limit))
    
    if df.empty:
        st.info("No invoices found.")
        return
    
    # Apply filters
    if invoice_search:
        df = df[df['invoice_number'].str.contains(invoice_search, case=False, na=False)]
    
    if vendor_search:
        df = df[df['vendor'].str.contains(vendor_search, case=False, na=False)]
    
    # Filter by invoice type
    if invoice_type_filter == "Commercial Invoice (CI)":
        df = df[df['invoice_number'].str.endswith('-P')]
    elif invoice_type_filter == "Advance Payment (PI)":
        df = df[df['invoice_number'].str.endswith('-A')]
    
    # Date filtering
    if date_filter != "Custom" and date_filter != "All Time":
        today = pd.Timestamp.now()
        if date_filter == "Last 7 days":
            date_threshold = today - timedelta(days=7)
        elif date_filter == "Last 30 days":
            date_threshold = today - timedelta(days=30)
        elif date_filter == "Last 90 days":
            date_threshold = today - timedelta(days=90)
        elif date_filter == "This Month":
            date_threshold = today.replace(day=1)
        
        if 'date_threshold' in locals():
            df['created_date'] = pd.to_datetime(df['created_date'])
            df = df[df['created_date'] >= date_threshold]
    elif date_filter == "Custom":
        if 'date_from' in locals() and 'date_to' in locals():
            df['created_date'] = pd.to_datetime(df['created_date'])
            df = df[(df['created_date'].dt.date >= date_from) & 
                   (df['created_date'].dt.date <= date_to)]
    
    # Add invoice type column based on suffix
    df['invoice_type'] = df['invoice_number'].apply(
        lambda x: 'Advance Payment' if x.endswith('-A') else 'Commercial Invoice'
    )
    
    # Summary metrics by currency
    st.markdown("### 📈 Summary")
    
    # Group by currency for summary
    currency_groups = df.groupby('currency')['total_invoiced_amount'].agg(['sum', 'count', 'mean'])
    
    # Display metrics for each currency
    cols = st.columns(min(len(currency_groups), 4))
    for idx, (currency, stats) in enumerate(currency_groups.iterrows()):
        col_idx = idx % 4
        with cols[col_idx]:
            st.metric(
                f"Total {currency}",
                f"{stats['sum']:,.2f}",
                f"{stats['count']} invoices"
            )
    
    # Additional summary row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Invoices", len(df))
    
    with col2:
        unique_vendors = df['vendor'].nunique()
        st.metric("Unique Vendors", unique_vendors)
    
    with col3:
        ci_count = len(df[df['invoice_type'] == 'Commercial Invoice'])
        st.metric("Commercial Invoices", ci_count)
    
    with col4:
        pi_count = len(df[df['invoice_type'] == 'Advance Payment'])
        st.metric("Advance Payments", pi_count)
    
    # Invoice table
    st.markdown("### 📋 Invoice List")
    
    # Format display
    df_display = df.copy()
    
    # Format dates
    if 'invoiced_date' in df_display.columns:
        df_display['invoiced_date'] = pd.to_datetime(df_display['invoiced_date']).dt.strftime('%Y-%m-%d')
    if 'due_date' in df_display.columns:
        df_display['due_date'] = pd.to_datetime(df_display['due_date']).dt.strftime('%Y-%m-%d')
    if 'created_date' in df_display.columns:
        df_display['created_date'] = pd.to_datetime(df_display['created_date']).dt.strftime('%Y-%m-%d %H:%M')
    
    # Format amount
    df_display['total_amount'] = df_display.apply(
        lambda row: f"{row['total_invoiced_amount']:,.2f} {row['currency']}", axis=1
    )
    
    # Select columns to display
    display_columns = [
        'invoice_number', 'invoice_type', 'commercial_invoice_no', 'invoiced_date', 
        'vendor', 'total_amount', 'line_count', 'po_count',
        'payment_term', 'due_date', 'created_by', 'created_date'
    ]
    
    # Remove commercial_invoice_no if not in dataframe
    if 'commercial_invoice_no' not in df_display.columns:
        display_columns.remove('commercial_invoice_no')
    
    # Rename columns for display
    column_mapping = {
        'invoice_number': 'Invoice #',
        'invoice_type': 'Type',
        'commercial_invoice_no': 'Commercial #',
        'invoiced_date': 'Invoice Date',
        'vendor': 'Vendor',
        'total_amount': 'Amount',
        'line_count': 'Lines',
        'po_count': 'POs',
        'payment_term': 'Payment Terms',
        'due_date': 'Due Date',
        'created_by': 'Created By',
        'created_date': 'Created'
    }
    
    # Filter columns that exist
    display_columns = [col for col in display_columns if col in df_display.columns]
    df_display = df_display[display_columns].rename(columns=column_mapping)
    
    # Display as dataframe
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    # Export options
    st.markdown("### 📥 Export Options")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export to Excel
        if st.button("📊 Export to Excel", use_container_width=True):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_display.to_excel(writer, sheet_name='Invoices', index=False)
            
            st.download_button(
                label="⬇️ Download Excel File",
                data=buffer.getvalue(),
                file_name=f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col2:
        # Export to CSV
        csv = df_display.to_csv(index=False)
        st.download_button(
            label="📄 Download CSV",
            data=csv,
            file_name=f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col3:
        # Summary report
        if st.button("📊 Generate Summary Report", use_container_width=True):
            report = f"""
PURCHASE INVOICE SUMMARY REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL SUMMARY:
- Total Invoices: {len(df)}
- Date Range: {df['invoiced_date'].min()} to {df['invoiced_date'].max()}
- Total Vendors: {df['vendor'].nunique()}

BY INVOICE TYPE:
- Commercial Invoices: {len(df[df['invoice_type'] == 'Commercial Invoice'])}
- Advance Payments: {len(df[df['invoice_type'] == 'Advance Payment'])}

BY CURRENCY:
"""
            for currency, stats in currency_groups.iterrows():
                report += f"\n{currency}:"
                report += f"\n  - Count: {int(stats['count'])}"
                report += f"\n  - Total: {stats['sum']:,.2f}"
                report += f"\n  - Average: {stats['mean']:,.2f}"
            
            st.download_button(
                label="⬇️ Download Report",
                data=report,
                file_name=f"invoice_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )

if __name__ == "__main__":
    main()