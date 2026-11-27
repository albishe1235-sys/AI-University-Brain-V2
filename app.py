
import streamlit as st
import sqlite3
import hashlib
import secrets
import os
from datetime import datetime

# إعدادات التطبيق
st.set_page_config(
    page_title="AI University Brain",
    page_icon="🎓",
    layout="wide"
)

DB_NAME = "university.db"


# إنشاء قاعدة البيانات
def get_connection():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS lectures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                university TEXT,
                department TEXT,
                stage TEXT,
                subject TEXT,
                doctor TEXT,
                content TEXT,
                file_name TEXT,
                upload_date TEXT
            )
        """)


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        200000
    ).hex()


def register_user(username, email, password, role):
    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO users
                (username, email, password_hash, salt, role)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, password_hash, salt, role))
        return True
    except sqlite3.IntegrityError:
        return False


def login_user(email, password):
    with get_connection() as conn:
        user = conn.execute("""
            SELECT id, username, email, password_hash, salt, role
            FROM users WHERE email = ?
        """, (email,)).fetchone()

    if user:
        entered_hash = hash_password(password, user[4])
        if secrets.compare_digest(user[3], entered_hash):
            return {
                "id": user[0],
                "username": user[1],
                "email": user[2],
                "role": user[5]
            }

    return None


# تشغيل قاعدة البيانات
initialize_database()


# واجهة المنصة
st.title("🎓 AI University Brain")
st.caption("منصة المعرفة الذكية للجامعة")
st.divider()


# حالة تسجيل الدخول
if "user" not in st.session_state:
    st.session_state.user = None


# صفحة تسجيل الدخول والتسجيل
if st.session_state.user is None:

    login_tab, register_tab = st.tabs([
        "تسجيل الدخول",
        "إنشاء حساب"
    ])

    with login_tab:
        st.subheader("تسجيل الدخول")

        email = st.text_input("البريد الإلكتروني")
        password = st.text_input(
            "كلمة المرور",
            type="password"
        )

        if st.button("دخول", use_container_width=True):
            user = login_user(email.strip(), password)

            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("البريد الإلكتروني أو كلمة المرور غير صحيحة")

    with register_tab:
        st.subheader("إنشاء حساب جديد")

        username = st.text_input("الاسم", key="reg_name")
        new_email = st.text_input("البريد الإلكتروني", key="reg_email")
        new_password = st.text_input(
            "كلمة المرور",
            type="password",
            key="reg_password"
        )

        confirm_password = st.text_input(
            "تأكيد كلمة المرور",
            type="password"
        )

        role = st.selectbox(
            "نوع الحساب",
            ["student", "doctor"],
            format_func=lambda x: {
                "student": "طالب",
                "doctor": "دكتور"
            }[x]
        )

        if st.button("إنشاء الحساب", use_container_width=True):
            if not username.strip() or not new_email.strip() or not new_password:
                st.warning("يرجى إكمال جميع الحقول")

            elif new_password != confirm_password:
                st.error("كلمتا المرور غير متطابقتين")

            elif len(new_password) < 8:
                st.error("كلمة المرور يجب أن تكون 8 أحرف على الأقل")

            else:
                success = register_user(
                    username.strip(),
                    new_email.strip(),
                    new_password,
                    role
                )

                if success:
                    st.success("تم إنشاء الحساب بنجاح، يمكنك تسجيل الدخول")
                else:
                    st.error("هذا البريد الإلكتروني مسجل مسبقاً")


# لوحة المستخدم
else:
    user = st.session_state.user

    st.success(f"أهلاً بك، {user['username']}")

    st.write(f"نوع الحساب: {user['role']}")

    if st.button("تسجيل الخروج"):
        st.session_state.user = None
        st.rerun()

    st.divider()

    # البحث عن المحاضرات
    st.subheader("🔎 البحث في المحاضرات")

    question = st.text_input("اكتب كلمة أو سؤالاً للبحث")

    if st.button("بحث"):
        if question.strip():
            with get_connection() as conn:
                results = conn.execute("""
                    SELECT title, subject, doctor, content
                    FROM lectures
                    WHERE content LIKE ?
                       OR title LIKE ?
                       OR subject LIKE ?
                """, (
                    f"%{question}%",
                    f"%{question}%",
                    f"%{question}%"
                )).fetchall()

            if results:
                for result in results:
                    with st.expander(result[0]):
                        st.write("المادة:", result[1])
                        st.write("الدكتور:", result[2])
                        st.write(result[3])
            else:
                st.warning("لم يتم العثور على نتائج")

    # رفع المحاضرات للدكاترة
    if user["role"] == "doctor":
        st.divider()
        st.subheader("📤 رفع محاضرة")

        uploaded_file = st.file_uploader(
            "اختر ملف المحاضرة",
            type=["txt"]
        )

        university = st.text_input("الجامعة")
        department = st.text_input("القسم")
        stage = st.text_input("المرحلة")
        subject = st.text_input("المادة")

        if st.button("رفع المحاضرة"):
            if uploaded_file and department and stage and subject:
                content = uploaded_file.getvalue().decode(
                    "utf-8",
                    errors="replace"
                )

                with get_connection() as conn:
                    conn.execute("""
                        INSERT INTO lectures
                        (title, university, department, stage,
                         subject, doctor, content, file_name, upload_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        uploaded_file.name,
                        university,
                        department,
                        stage,
                        subject,
                        user["username"],
                        content,
                        uploaded_file.name,
                        datetime.now().isoformat()
                    ))

                st.success("تم رفع المحاضرة وحفظها بنجاح")
            else:
                st.warning("يرجى اختيار الملف وإكمال المعلومات")
