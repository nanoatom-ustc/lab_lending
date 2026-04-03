# app.py
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px

# 页面配置
st.set_page_config(
    page_title="实验室物资管理系统",
    page_icon="🔬",
    layout="wide"
)

# 初始化数据库
def init_database():
    conn = sqlite3.connect('lab_materials.db')
    c = conn.cursor()
    
    # 物资表
    c.execute('''CREATE TABLE IF NOT EXISTS materials
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  category TEXT,
                  total_quantity INTEGER DEFAULT 0,
                  available_quantity INTEGER DEFAULT 0,
                  unit TEXT,
                  location TEXT,
                  created_time TIMESTAMP)''')
    
    # 借出/借入记录表
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  material_id INTEGER,
                  borrower_name TEXT NOT NULL,
                  transaction_type TEXT,  -- 'borrow' 或 'return'
                  quantity INTEGER,
                  borrow_time TIMESTAMP,
                  return_time TIMESTAMP,
                  status TEXT,  -- 'borrowed', 'returned'
                  notes TEXT,
                  FOREIGN KEY (material_id) REFERENCES materials (id))''')
    
    conn.commit()
    conn.close()

# 获取所有物资
def get_all_materials():
    conn = sqlite3.connect('lab_materials.db')
    df = pd.read_sql_query("SELECT * FROM materials ORDER BY id", conn)
    conn.close()
    return df

# 获取所有借出记录
def get_all_transactions(status=None):
    conn = sqlite3.connect('lab_materials.db')
    query = """
        SELECT t.*, m.name as material_name, m.unit 
        FROM transactions t
        JOIN materials m ON t.material_id = m.id
    """
    if status:
        query += f" WHERE t.status = '{status}'"
    query += " ORDER BY t.borrow_time DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 添加新物资
def add_material(name, category, quantity, unit, location):
    conn = sqlite3.connect('lab_materials.db')
    c = conn.cursor()
    c.execute("""INSERT INTO materials 
                 (name, category, total_quantity, available_quantity, unit, location, created_time)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (name, category, quantity, quantity, unit, location, datetime.now()))
    conn.commit()
    conn.close()

# 借出物资
def borrow_material(material_id, borrower_name, quantity, notes):
    conn = sqlite3.connect('lab_materials.db')
    c = conn.cursor()
    
    # 检查可用数量
    c.execute("SELECT available_quantity FROM materials WHERE id = ?", (material_id,))
    available = c.fetchone()[0]
    
    if available >= quantity:
        # 更新物资数量
        c.execute("UPDATE materials SET available_quantity = available_quantity - ? WHERE id = ?",
                 (quantity, material_id))
        
        # 添加借出记录
        c.execute("""INSERT INTO transactions 
                     (material_id, borrower_name, transaction_type, quantity, borrow_time, status, notes)
                     VALUES (?, ?, 'borrow', ?, ?, 'borrowed', ?)""",
                  (material_id, borrower_name, quantity, datetime.now(), notes))
        
        conn.commit()
        conn.close()
        return True, "借出成功"
    else:
        conn.close()
        return False, f"库存不足，当前可用数量：{available}"

# 归还物资
def return_material(transaction_id, return_quantity=None):
    conn = sqlite3.connect('lab_materials.db')
    c = conn.cursor()
    
    # 获取借出记录
    c.execute("SELECT material_id, quantity, status FROM transactions WHERE id = ?", (transaction_id,))
    result = c.fetchone()
    
    if result and result[2] == 'borrowed':
        material_id, borrowed_qty, _ = result
        
        # 如果没有指定归还数量，默认全部归还
        if return_quantity is None or return_quantity >= borrowed_qty:
            return_qty = borrowed_qty
            # 更新物资库存
            c.execute("UPDATE materials SET available_quantity = available_quantity + ? WHERE id = ?",
                     (borrowed_qty, material_id))
            # 更新记录状态
            c.execute("""UPDATE transactions 
                         SET return_time = ?, status = 'returned', quantity = ?
                         WHERE id = ?""",
                      (datetime.now(), borrowed_qty, transaction_id))
            success_msg = f"全部归还成功，共 {borrowed_qty} 件"
            success = True
        else:
            # 部分归还
            return_qty = return_quantity
            # 更新物资库存
            c.execute("UPDATE materials SET available_quantity = available_quantity + ? WHERE id = ?",
                     (return_qty, material_id))
            # 更新原记录数量
            new_quantity = borrowed_qty - return_qty
            c.execute("UPDATE transactions SET quantity = ? WHERE id = ?",
                     (new_quantity, transaction_id))
            # 创建部分归还记录
            c.execute("""INSERT INTO transactions 
                         (material_id, borrower_name, transaction_type, quantity, borrow_time, return_time, status, notes)
                         SELECT material_id, borrower_name, 'return', ?, borrow_time, ?, 'returned', notes
                         FROM transactions WHERE id = ?""",
                      (return_qty, datetime.now(), transaction_id))
            success_msg = f"部分归还成功，归还 {return_qty} 件，剩余 {new_quantity} 件未归还"
            success = True
        
        conn.commit()
        conn.close()
        return success, success_msg
    else:
        conn.close()
        return False, "记录不存在或已归还"

# 主页面
def main():
    st.title("🔬 实验室物资管理系统")
    st.markdown("---")
    
    # 侧边栏导航
    menu = st.sidebar.selectbox(
        "功能菜单",
        ["📊 仪表板", "📦 物资管理", "📤 物资借出", "📥 物资归还", "📋 借还记录", "📈 统计分析"]
    )
    
    # 初始化数据库
    init_database()
    
    if menu == "📊 仪表板":
        show_dashboard()
    elif menu == "📦 物资管理":
        show_material_management()
    elif menu == "📤 物资借出":
        show_borrow_interface()
    elif menu == "📥 物资归还":
        show_return_interface()
    elif menu == "📋 借还记录":
        show_transactions()
    elif menu == "📈 统计分析":
        show_statistics()

def show_dashboard():
    col1, col2, col3, col4 = st.columns(4)
    
    # 统计数据
    materials_df = get_all_materials()
    transactions_df = get_all_transactions()
    
    total_materials = len(materials_df)
    total_items = materials_df['total_quantity'].sum() if not materials_df.empty else 0
    borrowed_items = transactions_df[transactions_df['status'] == 'borrowed']['quantity'].sum() if not transactions_df.empty else 0
    active_borrows = len(transactions_df[transactions_df['status'] == 'borrowed']) if not transactions_df.empty else 0
    
    with col1:
        st.metric("物资种类", total_materials)
    with col2:
        st.metric("物资总数", total_items)
    with col3:
        st.metric("已借出数量", borrowed_items)
    with col4:
        st.metric("进行中借阅", active_borrows)
    
    st.markdown("---")
    
    # 最近借出记录
    st.subheader("📝 最近借出记录")
    if not transactions_df.empty:
        recent = transactions_df.head(10)[['borrower_name', 'material_name', 'quantity', 'borrow_time', 'status']]
        recent.columns = ['借用人', '物资名称', '数量', '借出时间', '状态']
        st.dataframe(recent, use_container_width=True)
    else:
        st.info("暂无借出记录")
    
    # 库存预警
    st.subheader("⚠️ 库存预警")
    if not materials_df.empty:
        low_stock = materials_df[materials_df['available_quantity'] < 5]
        if not low_stock.empty:
            st.warning("以下物资库存不足5件：")
            st.dataframe(low_stock[['name', 'available_quantity', 'unit']], use_container_width=True)
        else:
            st.success("所有物资库存充足")

def show_material_management():
    st.header("物资管理")
    
    # 添加新物资
    with st.expander("➕ 添加新物资", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            name = st.text_input("物资名称")
        with col2:
            category = st.selectbox("类别", ["仪器设备", "试剂耗材", "办公用品", "其他"])
        with col3:
            quantity = st.number_input("数量", min_value=0, step=1)
        with col4:
            unit = st.text_input("单位", value="件")
        
        location = st.text_input("存放位置")
        
        if st.button("添加物资", type="primary"):
            if name and quantity >= 0:
                add_material(name, category, quantity, unit, location)
                st.success(f"成功添加物资：{name}")
                st.rerun()
            else:
                st.error("请填写完整信息")
    
    # 显示现有物资
    st.subheader("📋 现有物资清单")
    materials_df = get_all_materials()
    
    if not materials_df.empty:
        # 搜索和筛选
        col1, col2 = st.columns(2)
        with col1:
            search = st.text_input("🔍 搜索物资", placeholder="输入物资名称...")
        with col2:
            category_filter = st.selectbox("筛选类别", ["全部"] + list(materials_df['category'].unique()))
        
        filtered_df = materials_df.copy()
        if search:
            filtered_df = filtered_df[filtered_df['name'].str.contains(search, case=False)]
        if category_filter != "全部":
            filtered_df = filtered_df[filtered_df['category'] == category_filter]
        
        # 显示表格
        display_df = filtered_df[['id', 'name', 'category', 'total_quantity', 'available_quantity', 'unit', 'location']]
        display_df.columns = ['ID', '名称', '类别', '总数', '可用数', '单位', '位置']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无物资，请先添加")

def show_borrow_interface():
    st.header("物资借出")
    
    materials_df = get_all_materials()
    available_materials = materials_df[materials_df['available_quantity'] > 0]
    
    if available_materials.empty:
        st.warning("没有可借出的物资")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        material_options = {f"{row['name']} (剩余: {row['available_quantity']}{row['unit']})": row['id'] 
                           for _, row in available_materials.iterrows()}
        selected_material = st.selectbox("选择物资", list(material_options.keys()))
        material_id = material_options[selected_material]
        
        # 获取最大可借数量
        max_qty = available_materials[available_materials['id'] == material_id]['available_quantity'].values[0]
        quantity = st.number_input("借出数量", min_value=1, max_value=int(max_qty), step=1)
    
    with col2:
        borrower_name = st.text_input("借用人姓名")
        notes = st.text_area("备注", placeholder="用途、预计归还时间等")
    
    if st.button("确认借出", type="primary"):
        if borrower_name and quantity > 0:
            success, message = borrow_material(material_id, borrower_name, quantity, notes)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
        else:
            st.error("请填写完整信息")

def show_return_interface():
    st.header("物资归还")
    
    # 获取所有未归还的借出记录
    borrowed_df = get_all_transactions(status='borrowed')
    
    if borrowed_df.empty:
        st.info("当前没有未归还的借出记录")
        return
    
    # 显示未归还记录
    st.subheader("未归还记录")
    display_df = borrowed_df[['id', 'borrower_name', 'material_name', 'quantity', 'unit', 'borrow_time', 'notes']]
    display_df.columns = ['记录ID', '借用人', '物资名称', '借出数量', '单位', '借出时间', '备注']
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # 归还操作
    st.subheader("归还操作")
    col1, col2 = st.columns(2)
    
    with col1:
        transaction_options = {f"{row['borrower_name']} - {row['material_name']} (借出:{row['quantity']}{row['unit']})": row['id'] 
                              for _, row in borrowed_df.iterrows()}
        selected_transaction = st.selectbox("选择借出记录", list(transaction_options.keys()))
        transaction_id = transaction_options[selected_transaction]
        
        # 获取借出数量
        borrowed_qty = borrowed_df[borrowed_df['id'] == transaction_id]['quantity'].values[0]
        return_quantity = st.number_input("归还数量", min_value=1, max_value=int(borrowed_qty), value=int(borrowed_qty), step=1)
    
    if st.button("确认归还", type="primary"):
        success, message = return_material(transaction_id, return_quantity)
        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

def show_transactions():
    st.header("借还记录")
    
    # 筛选选项
    filter_type = st.selectbox("筛选状态", ["全部", "进行中", "已归还"])
    
    transactions_df = get_all_transactions()
    
    if not transactions_df.empty:
        if filter_type == "进行中":
            transactions_df = transactions_df[transactions_df['status'] == 'borrowed']
        elif filter_type == "已归还":
            transactions_df = transactions_df[transactions_df['status'] == 'returned']
        
        # 显示记录
        display_df = transactions_df[['borrower_name', 'material_name', 'quantity', 'unit', 
                                     'borrow_time', 'return_time', 'status', 'notes']]
        display_df.columns = ['借用人', '物资名称', '数量', '单位', '借出时间', '归还时间', '状态', '备注']
        
        # 格式化时间
        display_df['借出时间'] = pd.to_datetime(display_df['借出时间']).dt.strftime('%Y-%m-%d %H:%M')
        display_df['归还时间'] = pd.to_datetime(display_df['归还时间']).dt.strftime('%Y-%m-%d %H:%M') if not display_df['归还时间'].isna().all() else ''
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # 导出功能
        if st.button("导出记录为CSV"):
            csv = transactions_df.to_csv(index=False)
            st.download_button("下载CSV", csv, "transactions.csv", "text/csv")
    else:
        st.info("暂无借还记录")

def show_statistics():
    st.header("统计分析")
    
    transactions_df = get_all_transactions()
    
    if transactions_df.empty:
        st.info("暂无数据")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 借出次数最多的物资
        st.subheader("最受欢迎物资")
        popular = transactions_df[transactions_df['status'] == 'borrowed']['material_name'].value_counts().head(10)
        if not popular.empty:
            fig = px.bar(x=popular.values, y=popular.index, orientation='h', 
                        title="借出次数最多的物资")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 借用人排行
        st.subheader("借用最频繁的人员")
        frequent_borrowers = transactions_df[transactions_df['status'] == 'borrowed']['borrower_name'].value_counts().head(10)
        if not frequent_borrowers.empty:
            fig = px.bar(x=frequent_borrowers.values, y=frequent_borrowers.index, orientation='h',
                        title="借用次数最多的人员")
            st.plotly_chart(fig, use_container_width=True)
    
    # 借出趋势
    st.subheader("借出趋势")
    transactions_df['borrow_date'] = pd.to_datetime(transactions_df['borrow_time']).dt.date
    daily_borrows = transactions_df.groupby('borrow_date').size().reset_index(name='count')
    if not daily_borrows.empty:
        fig = px.line(daily_borrows, x='borrow_date', y='count', title="每日借出数量趋势")
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
