import streamlit as st
import sqlite3
import pandas as pd
import time
import os
from git import Repo
from datetime import datetime, timedelta
from PIL import Image

# 1. 網頁基本設定 (標題已修改為製造部)
st.set_page_config(page_title="超慧製造部-雲端公佈欄", page_icon="🏭", layout="wide")

# --- 🚀 安全修改：改用 Streamlit Secrets ---
try:
    if "MY_TOKEN" in st.secrets:
        MY_TOKEN = st.secrets["MY_TOKEN"]
    else:
        st.error("❌ 找不到雲端金鑰！請在 Streamlit Settings > Secrets 設定 MY_TOKEN。")
        MY_TOKEN = ""
except Exception as e:
    st.error(f"讀取金鑰失敗: {e}")
    MY_TOKEN = ""

GITHUB_REPO = f"https://{MY_TOKEN}@github.com/ts700805-ops/my-bulletin-board.git"
IMAGE_FOLDER = "images"

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

# --- 標準同步功能 ---
def sync_to_github(commit_msg="Update"):
    if not MY_TOKEN:
        st.error("無法同步：缺少金鑰。")
        return
    try:
        os.environ["GIT_ASKPASS"] = "echo"
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        repo = Repo(".")
        if 'origin' in repo.remotes:
            repo.delete_remote('origin')
        origin = repo.create_remote('origin', GITHUB_REPO)
        repo.git.add("--all") 
        tw_now = (datetime.utcnow() + timedelta(hours=8)).strftime('%m/%d %H:%M')
        repo.index.commit(f"{commit_msg} - {tw_now}")
        origin.push(refspec='main:main', force=True)
        st.toast("✅ GitHub 同步備份成功")
    except Exception as e:
        st.error(f"同步失敗: {str(e)}")

# --- 資料庫工具 ---
def get_db_conn():
    return sqlite3.connect('bulletin.db', check_same_thread=False)

def init_db():
    conn = get_db_conn()
    c = conn.cursor()
    # 建立公告表
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  date TEXT, author TEXT, content TEXT, 
                  image_path TEXT, is_deleted INTEGER DEFAULT 0)''')
    # 新增：建立人員名單表
    c.execute('''CREATE TABLE IF NOT EXISTS staff 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    
    # 預設加入初始人員
    c.execute("INSERT OR IGNORE INTO staff (name) VALUES ('賴智文')")
    c.execute("INSERT OR IGNORE INTO staff (name) VALUES ('黃沂澂')")
    conn.commit()
    conn.close()

init_db()

# --- 側邊選單 ---
with st.sidebar:
    st.markdown("### 👤 目前登入\n## 管理員")
    st.markdown("---")
    menu = st.radio("功能選單", ["🏠 公佈欄首頁", "✍️ 撰寫新公告", "📜 所有公佈歷史紀錄", "⚙️ 管理後台"])

# 1. 修改標題為「製造部」
st.title("🏭 <超慧>製造部-雲端公佈欄")

# --- 介面邏輯 ---
if menu == "🏠 公佈欄首頁":
    try:
        df = pd.read_sql("SELECT * FROM posts WHERE is_deleted = 0 ORDER BY id DESC", get_db_conn())
        if df.empty:
            st.write("目前尚無公告")
        for _, row in df.iterrows():
            with st.container():
                st.markdown(f"**{row['date']} | 發布人：{row['author']}**")
                st.info(row['content'])
                if row['image_path'] and os.path.exists(row['image_path']):
                    with st.popover("🖼️ 檢視照片"):
                        st.image(Image.open(row['image_path']), use_container_width=True)
                st.markdown("---")
    except:
        st.write("資料庫讀取中...")

elif menu == "✍️ 撰寫新公告":
    st.subheader("📝 發布新訊息")
    
    # 2. 發布人員改成從資料庫抓取的下拉式選單
    conn = get_db_conn()
    staff_df = pd.read_sql("SELECT name FROM staff", conn)
    conn.close()
    author_list = staff_df['name'].tolist()
    
    author = st.selectbox("發布人", author_list)
    msg = st.text_area("公告內容", placeholder="請輸入內容...")
    file = st.file_uploader("🖼️ 上傳照片 (必填)", type=['jpg', 'png', 'jpeg'])
    
    if st.button("🚀 立即發布"):
        if msg and file:
            img_p = f"{IMAGE_FOLDER}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}"
            with open(img_p, "wb") as f:
                f.write(file.getbuffer())
            
            conn = get_db_conn()
            tw_time = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
            conn.execute("INSERT INTO posts (date, author, content, image_path, is_deleted) VALUES (?, ?, ?, ?, 0)", 
                         (tw_time, author, msg, img_p))
            conn.commit()
            conn.close()
            
            sync_to_github(f"New Post by {author}")
            st.success("發布成功！")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("請填寫內容並上傳照片。")

elif menu == "📜 所有公佈歷史紀錄":
    st.subheader("📅 歷史公告查詢")
    df = pd.read_sql("SELECT date, author, content FROM posts WHERE is_deleted = 0 ORDER BY id DESC", get_db_conn())
    st.dataframe(df, use_container_width=True)

elif menu == "⚙️ 管理後台":
    st.subheader("🛠️ 管理系統")
    
    # 3. 後台輸入密碼鎖
    pwd = st.text_input("請輸入管理密碼", type="password")
    
    if pwd == "0000":
        tab1, tab2 = st.tabs(["公告管理", "人員管理"])
        with tab1:
            df = pd.read_sql("SELECT * FROM posts WHERE is_deleted = 0 ORDER BY id DESC", get_db_conn())
            for _, row in df.iterrows():
                col1, col2 = st.columns([8, 2])
                col1.write(f"[{row['date']}] {row['content'][:30]}...")
                if col2.button("🗑️ 刪除", key=f"del_{row['id']}"):
                    conn = get_db_conn()
                    conn.execute("UPDATE posts SET is_deleted = 1 WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    sync_to_github(f"Delete Post {row['id']}")
                    st.rerun()
        with tab2:
            st.write("### 👥 人員名單管理")
            # 顯示目前名單
            conn = get_db_conn()
            current_staff = pd.read_sql("SELECT * FROM staff", conn)
            st.dataframe(current_staff[['name']], use_container_width=True)
            
            # 新增人員功能
            new_name = st.text_input("請輸入新人員姓名")
            if st.button("➕ 新增人員"):
                if new_name:
                    try:
                        conn.execute("INSERT INTO staff (name) VALUES (?)", (new_name,))
                        conn.commit()
                        sync_to_github(f"Add staff: {new_name}")
                        st.success(f"已成功新增：{new_name}")
                        time.sleep(1)
                        st.rerun()
                    except:
                        st.error("此人員已在名單中。")
                else:
                    st.warning("請輸入姓名。")
            conn.close()
    elif pwd != "":
        st.error("密碼錯誤，請重新輸入。")
