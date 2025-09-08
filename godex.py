import streamlit as st
import win32print
import win32ui
import win32con
import tempfile
import os
from PIL import Image, ImageDraw, ImageFont

# Cấu hình trang
st.set_page_config(
    page_title="Godex G500 Label Printer",
    page_icon="🏷️",
    layout="centered"
)

st.title("🏷️ Godex G500 Label Printer")
st.markdown("---")

# Hàm lấy danh sách máy in
@st.cache_data
def get_printers():
    printers = []
    for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
        printers.append(printer[2])
    return printers

# Hàm gửi lệnh EZPL trực tiếp đến máy in
def send_raw_data_to_printer(printer_name, raw_data):
    try:
        # Mở máy in
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            # Bắt đầu document
            hJob = win32print.StartDocPrinter(hPrinter, 1, ("Label", None, "RAW"))
            try:
                # Bắt đầu trang
                win32print.StartPagePrinter(hPrinter)
                # Gửi dữ liệu
                win32print.WritePrinter(hPrinter, raw_data.encode('utf-8'))
                # Kết thúc trang
                win32print.EndPagePrinter(hPrinter)
            finally:
                # Kết thúc document
                win32print.EndDocPrinter(hPrinter)
        finally:
            # Đóng máy in
            win32print.ClosePrinter(hPrinter)
        return True, "In thành công!"
    except Exception as e:
        return False, f"Lỗi: {str(e)}"

# Hàm tạo lệnh EZPL để in text
def create_ezpl_text_label(text, width=4, height=2):
    """
    Tạo lệnh EZPL để in nhãn text
    width, height: kích thước nhãn theo inch
    """
    ezpl_commands = f"""
^Q50,3
^W{int(width * 203)}
^H{int(height * 203)}
^P1
^S4
^AT
^C1
^R0
~Q+0
^O0
^D0
^E18
^L
Dy2-me-dd
Th:m:s
AA,50,100,1,1,0,0,{text}
E
"""
    return ezpl_commands

# Hàm tạo lệnh EZPL cho barcode
def create_ezpl_barcode_label(text, barcode_text, width=4, height=2):
    """
    Tạo lệnh EZPL để in nhãn với barcode
    """
    ezpl_commands = f"""
^Q50,3
^W{int(width * 203)}
^H{int(height * 203)}
^P1
^S4
^AT
^C1
^R0
~Q+0
^O0
^D0
^E18
^L
Dy2-me-dd
Th:m:s
AA,50,50,1,1,0,0,{text}
BA,50,150,2,5,100,0,3,{barcode_text}
E
"""
    return ezpl_commands

# Main UI
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🖨️ Chọn máy in")
    printers = get_printers()
    
    # Tìm máy in Godex G500
    godex_printer = None
    for printer in printers:
        if "Godex G500" in printer:
            godex_printer = printer
            break
    
    if godex_printer:
        selected_printer = st.selectbox(
            "Máy in có sẵn:",
            printers,
            index=printers.index(godex_printer)
        )
    else:
        selected_printer = st.selectbox("Máy in có sẵn:", printers)
        st.warning("⚠️ Không tìm thấy máy in Godex G500!")

with col2:
    st.subheader("📏 Kích thước nhãn")
    label_width = st.number_input("Chiều rộng (inch)", min_value=1.0, max_value=4.0, value=2.0, step=0.5)
    label_height = st.number_input("Chiều cao (inch)", min_value=1.0, max_value=6.0, value=1.0, step=0.5)

st.markdown("---")

# Tabs cho các chức năng khác nhau
tab1, tab2, tab3, tab4 = st.tabs(["✏️ In Text", "📊 In Barcode", "🧪 Test Kết Nối", "📝 Lệnh EZPL Tùy Chỉnh"])

with tab1:
    st.subheader("In nhãn với text")
    text_content = st.text_area("Nhập nội dung text:", "Hello from Streamlit!\nGodex G500 Test")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🖨️ In Text Label", type="primary", use_container_width=True):
            if selected_printer:
                ezpl_cmd = create_ezpl_text_label(text_content, label_width, label_height)
                success, message = send_raw_data_to_printer(selected_printer, ezpl_cmd)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.error("Vui lòng chọn máy in!")
    
    with col2:
        if st.button("👁️ Xem lệnh EZPL", use_container_width=True):
            ezpl_cmd = create_ezpl_text_label(text_content, label_width, label_height)
            st.code(ezpl_cmd, language="text")

with tab2:
    st.subheader("In nhãn với Barcode")
    barcode_title = st.text_input("Tiêu đề:", "Product Label")
    barcode_data = st.text_input("Dữ liệu Barcode:", "123456789012")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🖨️ In Barcode Label", type="primary", use_container_width=True):
            if selected_printer:
                ezpl_cmd = create_ezpl_barcode_label(barcode_title, barcode_data, label_width, label_height)
                success, message = send_raw_data_to_printer(selected_printer, ezpl_cmd)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.error("Vui lòng chọn máy in!")
    
    with col2:
        if st.button("👁️ Xem lệnh EZPL ", use_container_width=True):
            ezpl_cmd = create_ezpl_barcode_label(barcode_title, barcode_data, label_width, label_height)
            st.code(ezpl_cmd, language="text")

with tab3:
    st.subheader("Test kết nối máy in")
    st.info("🔌 Click nút bên dưới để test kết nối và in một nhãn test")
    
    if st.button("🧪 Test Print", type="primary", use_container_width=True):
        if selected_printer:
            # Lệnh EZPL đơn giản để test
            test_ezpl = """
^Q50,3
^W406
^H203
^P1
^S4
^AT
^C1
^R0
~Q+0
^O0
^D0
^E18
^L
Dy2-me-dd
Th:m:s
AA,50,50,1,1,0,0,GODEX G500 TEST
AA,50,100,1,1,0,0,Connection OK!
E
"""
            success, message = send_raw_data_to_printer(selected_printer, test_ezpl)
            if success:
                st.success("✅ " + message)
                st.balloons()
            else:
                st.error("❌ " + message)
        else:
            st.error("Vui lòng chọn máy in!")

with tab4:
    st.subheader("Gửi lệnh EZPL tùy chỉnh")
    st.warning("⚠️ Chỉ sử dụng nếu bạn biết cú pháp EZPL!")
    
    custom_ezpl = st.text_area(
        "Nhập lệnh EZPL:",
        value="""^Q50,3
^W406
^H203
^P1
^S4
^AT
^C1
^R0
~Q+0
^O0
^D0
^E18
^L
Dy2-me-dd
Th:m:s
AA,50,50,1,1,0,0,Custom EZPL Command
E""",
        height=300
    )
    
    if st.button("🚀 Gửi lệnh EZPL", type="primary", use_container_width=True):
        if selected_printer:
            success, message = send_raw_data_to_printer(selected_printer, custom_ezpl)
            if success:
                st.success(message)
            else:
                st.error(message)
        else:
            st.error("Vui lòng chọn máy in!")

# Sidebar với thông tin
with st.sidebar:
    st.header("📖 Hướng dẫn")
    st.markdown("""
    ### Cách sử dụng:
    1. **Chọn máy in** Godex G500 từ danh sách
    2. **Cài đặt kích thước** nhãn phù hợp
    3. **Chọn tab** chức năng muốn sử dụng:
       - **In Text**: In nhãn với text đơn giản
       - **In Barcode**: In nhãn có barcode
       - **Test Kết Nối**: Kiểm tra kết nối máy in
       - **Lệnh EZPL**: Gửi lệnh EZPL tùy chỉnh
    
    ### Lưu ý:
    - Đảm bảo máy in đã được bật và kết nối
    - Kiểm tra giấy in đã được nạp đúng cách
    - EZPL là ngôn ngữ lệnh của Godex
    """)
    
    st.markdown("---")
    st.markdown("### 🛠️ Thông tin kỹ thuật")
    st.code("""
    # Cài đặt thư viện cần thiết:
    pip install streamlit
    pip install pywin32
    pip install Pillow
    """)

# Footer
st.markdown("---")
st.caption("🏷️ Godex G500 Label Printer App - Developed with Streamlit")