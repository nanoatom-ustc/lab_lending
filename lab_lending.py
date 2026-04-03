import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px
import os

# ---------- 1. 页面配置 ----------
st.set_page_config(
    page_title="8004 实验室物资管理系统",
    page_icon="📋",
    layout="wide"
)

# 自定义 CSS：强化表格对比度，按钮颜色统一，侧边栏精简化
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    div[data-testid="stExpander"] { background-color: #ffffff; border-radius: 10px; }
    </style>
""", unsafe_allow_index=True)

# ---------- 2. 数据库逻辑 ----------
DB_NAME = 'lab_inventory.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # 物资基础信息表
        c.execute('''CREATE TABLE IF NOT EXISTS materials
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      category TEXT,
                      total_qty INTEGER DEFAULT 0,
                      available_qty INTEGER DEFAULT 0,
                      unit TEXT,
                      location TEXT,
                      update_time TIMESTAMP)''')
        # 借还流水记录表
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      material_id INTEGER,
                      user_name TEXT NOT NULL,
                      type TEXT, -- 'borrow' or 'return'
                      qty INTEGER,
                      time TIMESTAMP,
                      status TEXT, -- 'active' or 'closed'
                      notes TEXT,
                      FOREIGN KEY (material_id) REFERENCES materials (id))''')
        conn.commit()

def get_data(query):
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query(query, conn)

def execute_db(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()

# ---------- 3. 业务功能函数 ----------
def borrow_item(m_id, user, qty, note):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT available_qty FROM materials WHERE id = ?", (m_id,))
        current_avail = c.fetchone()[0]
        if current_avail >= qty:
            # 更新库存
            c.execute("UPDATE materials SET available_qty = available_qty - ? WHERE id = ?", (qty, m_id))
            # 插入记录
            c.execute("INSERT INTO transactions (material_id, user_name, type, qty, time, status, notes) VALUES (?, ?, 'borrow', ?, ?, 'active', ?)",
                      (m_id, user, qty, datetime.now(), note))
            conn.commit()
            return True, "借出登记成功"
        return False, "库存不足"

def return_item(t_id, r_qty):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT material_id, qty FROM transactions WHERE id = ?", (t_id,))
        res = c.fetchone()
        if res:
            m_id, b_qty = res
            # 更新库存
            c.execute("UPDATE materials SET available_qty = available_qty + ? WHERE id = ?", (r_qty, m_id))
            # 更新/关闭原借出记录
            if r_qty >= b_qty:
                c.execute("UPDATE transactions SET status = 'closed', time = ? WHERE id = ?", (datetime.now(), t_id))
            else:
                c.execute("UPDATE transactions SET qty = qty - ? WHERE id = ?", (r_qty, t_id))
            conn.commit()
            return True, "归还登记成功"
        return False, "未找到记录"

# ---------- 4. 各模块界面 ----------
def show_dashboard():
    st.subheader("📊 运行概况")
    m_df = get_data("SELECT * FROM materials")
    t_df = get_data("SELECT * FROM transactions WHERE status = 'active'")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("物资种类", len(m_df))
    col2.metric("在库总件数", m_df['available_qty'].sum() if not m_df.empty else 0)
    col3.metric("外部借出中", t_df['qty'].sum() if not t_df.empty else 0)
    col4.metric("未结清流程", len(t_df))

    st.markdown("---")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("🔍 库存快速查询")
        search = st.text_input("输入关键词搜索物资...", placeholder="零件名、型号、位置...")
        if not m_df.empty:
            display_m = m_df[['name', 'category', 'available_qty', 'unit', 'location']]
            if search:
                display_m = display_m[display_m['name'].str.contains(search, case=False) | display_m['location'].str.contains(search, case=False)]
            st.dataframe(display_m, use_container_width=True, hide_index=True)

    with c2:
        st.subheader("⚠️ 库存预警")
        low_stock = m_df[m_df['available_qty'] < 5]
        if not low_stock.empty:
            st.error("以下物资库存不足 5 件：")
            st.table(low_stock[['name', 'available_qty']])
        else:
            st.success("所有物资库存充足")

def show_management():
    st.subheader("📦 物资入库与编辑")
    with st.expander("➕ 新增物资条目"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("物资名称/型号")
        cat = c2.selectbox("分类", ["光学件", "机械件", "电子/射频", "耗材", "办公用品"])
        qty = c3.number_input("初始总库存", min_value=1, step=1)
        c4, c5 = st.columns(2)
        unit = c4.text_input("单位", value="件")
        loc = c5.text_input("存放位置")
        if st.button("提交入库"):
            if name:
                execute_db("INSERT INTO materials (name, category, total_qty, available_qty, unit, location, update_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (name, cat, qty, qty, unit, loc, datetime.now()))
                st.success(f"{name} 已入库")
                st.rerun()

    st.subheader("🛠️ 基础数据管理")
    m_df = get_data("SELECT * FROM materials")
    if not m_df.empty:
        # 使用 data_editor 允许用户直接在表格里修数据
        edited_df = st.data_editor(m_df, num_rows="dynamic", use_container_width=True, key="m_editor")
        if st.button("保存基础表修改"):
            # 这里简单演示：直接将编辑后的表覆盖回数据库（实际生产建议逐行对比）
            with sqlite3.connect(DB_NAME) as conn:
                edited_df.to_sql('materials', conn, if_exists='replace', index=False)
            st.success("基础数据已更新")
            st.rerun()

def show_borrow_return():
    tab1, tab2 = st.tabs(["📤 借出登记", "📥 归还入库"])
    
    with tab1:
        m_df = get_data("SELECT id, name, available_qty, unit FROM materials WHERE available_qty > 0")
        if m_df.empty:
            st.info("暂无库存可借出")
        else:
            with st.form("borrow_form"):
                m_list = {f"{r['name']} (剩余 {r['available_qty']} {r['unit']})": r['id'] for _, r in m_df.iterrows()}
                target = st.selectbox("选择物资", list(m_list.keys()))
                user = st.text_input("借用人姓名")
                b_qty = st.number_input("借出数量", min_value=1, step=1)
                note = st.text_area("用途/备注")
                if st.form_submit_button("确认借出"):
                    if user:
                        success, msg = borrow_item(m_list[target], user, b_qty, note)
                        if success: st.success(msg); st.rerun()
                        else: st.error(msg)
                    else: st.error("请填写借用人")

    with tab2:
        t_df = get_data("""SELECT t.id, t.user_name, m.name as m_name, t.qty, m.unit 
                           FROM transactions t JOIN materials m ON t.material_id = m.id 
                           WHERE t.status = 'active'""")
        if t_df.empty:
            st.info("当前无待归还物资")
        else:
            with st.form("return_form"):
                t_list = {f"{r['user_name']} - {r['m_name']} ({r['qty']} {r['unit']})": r['id'] for _, r in t_df.iterrows()}
                target_t = st.selectbox("选择待归还记录", list(t_list.keys()))
                r_qty = st.number_input("归还数量", min_value=1, step=1)
                if st.form_submit_button("确认归还"):
                    success, msg = return_item(t_list[target_t], r_qty)
                    if success: st.success(msg); st.rerun()
                    else: st.error(msg)

def show_logs():
    st.subheader("📋 历史操作流水")
    query = """
        SELECT t.user_name as 人员, m.name as 物资, t.type as 类型, t.qty as 数量, 
               t.time as 操作时间, t.status as 状态, t.notes as 备注
        FROM transactions t
        JOIN materials m ON t.material_id = m.id
        ORDER BY t.time DESC
    """
    logs_df = get_data(query)
    st.dataframe(logs_df, use_container_width=True)
    
    if st.button("导出为 CSV"):
        logs_df.to_csv("lab_history_logs.csv", index=False)
        st.success("已生成 lab_history_logs.csv 文件")

# ---------- 5. 主程序入口 ----------
def main():
    init_db()
    
    st.sidebar.title("8004 实验室管理")
    menu = st.sidebar.radio("功能菜单", ["📊 统计仪表板", "📦 物资管理", "🔃 借还登记", "📋 历史审计"])
    
    if menu == "📊 统计仪表板":
        show_dashboard()
    elif menu == "📦 物资管理":
        show_management()
    elif menu == "🔃 借还登记":
        show_borrow_return()
    elif menu == "📋 历史审计":
        show_logs()

if __name__ == "__main__":
    main()
