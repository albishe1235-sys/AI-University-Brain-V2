
import streamlit as st
import extra_streamlit_components as stx
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
import csv
from io import BytesIO, StringIO
from pypdf import PdfReader
from docx import Document
from pptx import Presentation
# إعدادات المنصة

st.set_page_config(
    page_title="AI University Brain",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)
cookie_manager = stx.CookieManager(key="auth_cookie_manager")
st.markdown("""
<style>
/* جعل الكتابة باللون الأسود */
.stApp,
.stApp label,
.stApp p,
.stApp h1,
.stApp h2,
.stApp h3,
.stTabs button,
.stTextInput input,
.stMarkdown {
    color: #000000 !important;
}

.stTextInput input {
    background-color: #FFFFFF !important;
    border: 1px solid #999999 !important;
}
    .stApp {
        background: #F4F7FC;
        color: #172554;
        direction: rtl;
    }

    [data-testid="stSidebar"] {
        background: #102A56;
    }

    [data-testid="stSidebar"] * {
        color: white;
    }

    h1, h2, h3 {
        color: #163B70;
        font-weight: 800;
    }

    .stButton > button {
        background: linear-gradient(90deg, #2457A7, #477DE0);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 10px 22px;
        font-weight: bold;
    }

    .stButton > button:hover {
        background: #173F7A;
        color: white;
        border: none;
    }

    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        border-radius: 10px;
    }

    [data-testid="stMetric"] {
        background: white;
        padding: 18px;
        border-radius: 14px;
        border: 1px solid #E0E8F5;
    }

    [data-testid="stExpander"] {
        background: white;
        border-radius: 12px;
        border: 1px solid #DCE6F5;
    }
</style>
""", unsafe_allow_html=True)

DB_NAME = "university.db"

ADMIN_EMAIL = "b6927572@gmail.com"


# الاتصال بقاعدة البيانات
def get_connection():
    return sqlite3.connect(DB_NAME)


# إنشاء الجداول
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
                upload_date TEXT
            )
        """)
        # جدول جلسات تسجيل الدخول
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
           )
        """)
        columns = [
            row[1] for row in conn.execute(
                "PRAGMA table_info(lectures)"
            ).fetchall()
        ]

        if "file_data" not in columns:
            conn.execute(
                "ALTER TABLE lectures ADD COLUMN file_data BLOB"
            )

        if "file_type" not in columns:
            conn.execute(
                "ALTER TABLE lectures ADD COLUMN file_type TEXT"
            )

# تشفير كلمة المرور
def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        200000
    ).hex()


# إنشاء حساب
def register_user(username, email, password, role):

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO users
                (username, email, password_hash, salt, role)
                VALUES (?, ?, ?, ?, ?)
            """, (
                username,
                email,
                password_hash,
                salt,
                role
            ))

        return True

    except sqlite3.IntegrityError:
        return False


# تسجيل الدخول
def login_user(email, password):

    with get_connection() as conn:
        user = conn.execute("""
            SELECT id, username, email, password_hash, salt, role
            FROM users
            WHERE email = ?
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

# قراءة الملفات واستخراج النص
def extract_text(uploaded_file):
    file_type = uploaded_file.name.split(".")[-1].lower()

    if file_type == "txt":
        return uploaded_file.getvalue().decode("utf-8", errors="replace")

    elif file_type == "pdf":
        pdf = PdfReader(BytesIO(uploaded_file.getvalue()))
        return "\n".join(
            page.extract_text() or "" for page in pdf.pages
        )

    elif file_type == "docx":
        doc = Document(BytesIO(uploaded_file.getvalue()))
        return "\n".join(p.text for p in doc.paragraphs)

    elif file_type == "pptx":
        presentation = Presentation(BytesIO(uploaded_file.getvalue()))
        return "\n".join(
            shape.text
            for slide in presentation.slides
            for shape in slide.shapes
            if shape.has_text_frame
        )

    elif file_type == "csv":
        content = uploaded_file.getvalue().decode("utf-8-sig", errors="replace")
        reader = csv.reader(StringIO(content))
        return "\n".join(" | ".join(row) for row in reader)

    return ""
# البحث في المحاضرات
def search_lectures(question):

    with get_connection() as conn:
        results = conn.execute("""
            SELECT title, subject, doctor, content, file_data, file_type
            FROM lectures
            WHERE content LIKE ?
               OR title LIKE ?
               OR subject LIKE ?
        """, (
            f"%{question}%",
            f"%{question}%",
            f"%{question}%"
        )).fetchall()

    return results
# إنشاء جلسة تسجيل الدخول
def create_login_session(user_id):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    now = datetime.now()
    expires = now + timedelta(days=30)

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO login_sessions
            (user_id, token_hash, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            token_hash,
            expires.isoformat(),
            now.isoformat()
        ))

    return token


# التحقق من جلسة تسجيل الدخول
def get_login_session(token):
    if not token:
        return None

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with get_connection() as conn:
        session = conn.execute("""
            SELECT users.id, users.username, users.email, users.role
            FROM login_sessions
            JOIN users ON users.id = login_sessions.user_id
            WHERE login_sessions.token_hash = ?
              AND login_sessions.expires_at > ?
        """, (token_hash, datetime.now().isoformat())).fetchone()

    if session:
        return {
            "id": session[0],
            "username": session[1],
            "email": session[2],
            "role": session[3]
        }

    return None

# تشغيل قاعدة البيانات
initialize_database()
def create_admin_account():
    try:
        admin_password = st.secrets["ADMIN_PASSWORD"]

        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                (ADMIN_EMAIL,)
            ).fetchone()

            if not existing:
                salt = secrets.token_hex(16)
                password_hash = hash_password(admin_password, salt)

                conn.execute("""
                    INSERT INTO users
                    (username, email, password_hash, salt, role)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    "Admin",
                    ADMIN_EMAIL,
                    password_hash,
                    salt,
                    "admin"
                ))

    except Exception:
        st.error("تعذر إعداد حساب الأدمن. راجع إعدادات المنصة.")


create_admin_account()

# واجهة المنصة
st.title("🎓 AI University Brain")
st.caption("منصة المعرفة الذكية للجامعة")
st.divider()


# حالة المستخدم
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    saved_token = cookie_manager.get("auth_token")
    restored_user = get_login_session(saved_token)

    if restored_user:
        st.session_state.user = restored_user

# صفحة الدخول والتسجيل

if st.session_state.user is None:

    st.markdown("""
        <div style="text-align:center; padding:35px 10px 20px;">
            <div style="font-size:55px;">🎓</div>
            <h1 style="color:#163B70; font-size:36px;">
                AI University Brain
            </h1>
            <p style="color:#64748B; font-size:17px;">
                منصتك الذكية لإدارة المحاضرات والبحث العلمي
            </p>
            
        </div>
    """, unsafe_allow_html=True)

    space1, center, space2 = st.columns([1, 2, 1])

    with center:

        st.markdown("""
            <div style="
                background:white;
                padding:12px;
                border-radius:16px;
                text-align:center;
                border:1px solid #DCE6F5;
                margin-bottom:15px;">
                <h3 style="color:#163B70;">مرحباً بك 👋</h3>
                <p style="color:#64748B;">
                    سجّل دخولك أو أنشئ حساباً جديداً للمتابعة
                </p>
            </div>
        """, unsafe_allow_html=True)

        login_tab, register_tab = st.tabs([
            "🔐 تسجيل الدخول",
            "📝 إنشاء حساب جديد"
        ])

                # تسجيل الدخول
        with login_tab:

            st.subheader("أهلاً بعودتك")

            email = st.text_input(
                "البريد الإلكتروني",
                key="login_email"
            )

            password = st.text_input(
                "كلمة المرور",
                type="password",
                key="login_password"
            )

            if st.button("دخول إلى المنصة", use_container_width=True):

                user = login_user(
                    email.strip().lower(),
                    password
                )

                if user:
                    token = create_login_session(user["id"])

                    cookie_manager.set(
                        "auth_token",
                        token,
                        expires_at=datetime.now() + timedelta(days=30)
                    )

                    st.session_state.user = user
                    st.rerun()

                else:
                    st.error(
                        "البريد الإلكتروني أو كلمة المرور غير صحيحة"
                    )
    
# لوحة المستخدم
else:

    user = st.session_state.user

    st.success(f"أهلاً بك، {user['username']}")

    st.write(
        "نوع الحساب:",
        "أدمن" if user["role"] == "admin"
        else "طالب" if user["role"] == "student"
        else "دكتور"
    )
     
    if st.button("تسجيل الخروج"):
        cookie_manager.delete("auth_token")

        with get_connection() as conn:
            conn.execute(
                "DELETE FROM login_sessions WHERE user_id = ?",
                (user["id"],)
            )

        st.session_state.user = None
        st.rerun()

    if user["role"] == "admin":
        st.divider()
        st.header("🛠️ لوحة تحكم الأدمن")
        st.success("أنت مسؤول المنصة")

        with get_connection() as conn:
            users_count = conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]

            lectures_count = conn.execute(
                "SELECT COUNT(*) FROM lectures"
            ).fetchone()[0]

        col1, col2 = st.columns(2)
        col1.metric("عدد المستخدمين", users_count)
        col2.metric("عدد المحاضرات", lectures_count)
        st.divider()
        st.subheader("👨‍🏫 إدارة صلاحيات الدكاترة")

        with get_connection() as conn:
            students = conn.execute(
                "SELECT id, username, email FROM users WHERE role = 'student'"
            ).fetchall()

        if students:
            selected_student = st.selectbox(
                "اختر الطالب لمنحه صلاحية دكتور",
                students,
                format_func=lambda x: f"{x[1]} - {x[2]}"
            )
        if st.button("منح صلاحية دكتور"):
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE users SET role = 'doctor' WHERE id = ?",
                        (selected_student[0],)
                    )

                st.success(
                    f"تم منح {selected_student[1]} صلاحية دكتور"
                )
                st.rerun()

    
    st.divider()

    st.subheader("🔎 البحث في المحاضرات")

    question = st.text_input(
        "اكتب كلمة أو سؤالاً للبحث"
    )

    if st.button("بحث"):

        if question.strip():

            results = search_lectures(question.strip())

            if results:

                for result in results:

                    with st.expander(result[0]):

                        st.write("المادة:", result[1])
                        st.write("الدكتور:", result[2])
                        st.write("محتوى المحاضرة:")
                        st.write(result[3])

                        if result[4]:
                            mime_types = {
                                "pdf": "application/pdf",
                                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "txt": "text/plain",
                                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                "csv": "text/csv"
                            }

                            st.download_button(
                                label="📥 تحميل المحاضرة الأصلية",
                                data=result[4],
                                file_name=result[0],
                                mime=mime_types.get(result[5], "application/octet-stream"),
key=f"download_{result[0]}_{result[1]}"
                            )

            else:
                st.warning("لم يتم العثور على نتائج")

        # رفع المحاضرات للدكتور
    if user["role"] == "doctor":

        st.divider()
        st.subheader("📤 رفع محاضرة")

        uploaded_file = st.file_uploader(
            "اختر ملف المحاضرة",
            type=["pdf", "docx", "txt", "pptx", "csv"]
        )

        university = st.text_input(
            "الجامعة",
            value="University of the Future"
        )

        department = st.text_input("القسم")
        stage = st.text_input("المرحلة")
        subject = st.text_input("المادة")

        if st.button("رفع وحفظ المحاضرة"):

            if uploaded_file and department and stage and subject:

                content = extract_text(uploaded_file)
                file_data = uploaded_file.getvalue()
                file_type = uploaded_file.name.split(".")[-1].lower()

                with get_connection() as conn:
                    conn.execute("""
                        INSERT INTO lectures
                        (title, university, department, stage,
                         subject, doctor, content, upload_date,
                         file_data, file_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        uploaded_file.name,
                        university,
                        department,
                        stage,
                        subject,
                        user["username"],
                        content,
                        datetime.now().isoformat(),
                        file_data,
                        file_type
                    ))

                st.success("تم رفع المحاضرة وحفظها بنجاح")

            else:
               st.warning("يرجى اختيار الملف وإكمال المعلومات")
        st.divider()
        st.subheader("🗑️ حذف محاضرة")

        with get_connection() as conn:
            doctor_lectures = conn.execute(
                "SELECT id, title, subject FROM lectures WHERE doctor = ?",
                (user["username"],)
            ).fetchall()

        if doctor_lectures:

            selected_lecture = st.selectbox(
                "اختر المحاضرة التي تريد حذفها",
                doctor_lectures,
                format_func=lambda x: f"{x[1]} - {x[2]}"
            )

            if st.button("حذف المحاضرة"):

                with get_connection() as conn:
                    conn.execute(
                        "DELETE FROM lectures WHERE id = ? AND doctor = ?",
                        (selected_lecture[0], user["username"])
                    )

                st.success("تم حذف المحاضرة بنجاح")
                st.rerun()

        else:
            st.info("لا توجد محاضرات مرفوعة من حسابك")
