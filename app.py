
import streamlit as st
import sqlite3
import hashlib
import secrets
from datetime import datetime
import csv
from io import BytesIO, StringIO
from pypdf import PdfReader
from docx import Document
from pptx import Presentation
# إعدادات المنصة
st.set_page_config(
    page_title="AI University Brain",
    page_icon="🎓",
    layout="wide"
)

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


# صفحة الدخول والتسجيل
if st.session_state.user is None:

    login_tab, register_tab = st.tabs([
        "تسجيل الدخول",
        "إنشاء حساب جديد"
    ])

    # تسجيل الدخول
    with login_tab:

        st.subheader("تسجيل الدخول")

        email = st.text_input(
            "البريد الإلكتروني",
            key="login_email"
        )

        password = st.text_input(
            "كلمة المرور",
            type="password",
            key="login_password"
        )

        if st.button("دخول", use_container_width=True):

            user = login_user(
                email.strip().lower(),
                password
            )

            if user:
                st.session_state.user = user
                st.rerun()

            else:
                st.error(
                    "البريد الإلكتروني أو كلمة المرور غير صحيحة"
                )

    # إنشاء حساب جديد
    with register_tab:

        st.subheader(".إنشاء حساب جديد")

        username = st.text_input(
            "الاسم",
            key="register_name"
        )

        new_email = st.text_input(
            "البريد الإلكتروني",
            key="register_email"
        )

        new_password = st.text_input(
            "كلمة المرور",
            type="password",
            key="register_password"
        )

        confirm_password = st.text_input(
            "تأكيد كلمة المرور",
            type="password",
            key="confirm_password"
        )

        role = "student"

        if st.button(
            "إنشاء الحساب",
            use_container_width=True
        ):

            if not username.strip() or not new_email.strip() or not new_password:
                st.warning("يرجى إكمال جميع الحقول")

            elif new_password != confirm_password:
                st.error("كلمتا المرور غير متطابقتين")

            elif len(new_password) < 8:
                st.error("كلمة المرور يجب أن تكون 8 أحرف على الأقل")

            else:

                success = register_user(
                    username.strip(),
                    new_email.strip().lower(),
                    new_password,
                    role
                )

                if success:
                    st.success(
                        "تم إنشاء الحساب بنجاح، يمكنك تسجيل الدخول"
                    )

                else:
                    st.error(
                        "هذا البريد الإلكتروني مسجل مسبقاً"
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
                                mime=mime_types.get(result[5], "application/octet-stream")
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
