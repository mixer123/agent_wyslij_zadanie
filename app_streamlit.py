import streamlit as st
import requests
from streamlit_oauth import OAuth2Component
import gspread, re
from oauth2client.service_account import ServiceAccountCredentials


# -------- GOOGLE OAUTH --------

CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

REDIRECT_URI = st.secrets["REDIRECT_URI"]

WEBHOOK_URL = st.secrets["WEBHOOK_URL"]

oauth2 = OAuth2Component(
    CLIENT_ID,
    CLIENT_SECRET,
    AUTHORIZE_URL,
    TOKEN_URL,
)

# -------- FUNKCJA SPRAWDZAJĄCA POPRAWNOŚĆ EMAILA --------
def poprawny_email(email):
    wzorzec = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(wzorzec, email)

# -------- FUNKCJA POBIERANIA UCZNIÓW --------
@st.cache_data(ttl=300)
def pobierz_uczniow():

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_dict = json.loads(st.secrets["gcp_service_account"])

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    client = gspread.authorize(creds)

    sheet = client.open("klasy_login_haslo").sheet1

    dane = sheet.get_all_records()

    uczniowie = {}

    for wiersz in dane:
        uczniowie[str(wiersz["login"])] = str(wiersz["haslo"])

    return uczniowie


# -------- SESSION --------

if "zalogowany" not in st.session_state:
    st.session_state.zalogowany = False

if "login" not in st.session_state:
    st.session_state.login = None

if "wyslano" not in st.session_state:
    st.session_state.wyslano = False


# -------- LOGOWANIE --------

if not st.session_state.zalogowany:

    st.title("Logowanie ucznia")

    # -------- GOOGLE LOGIN --------

    # result = oauth2.authorize_button(
    #     name="Zaloguj przez Google",
    #     redirect_uri=REDIRECT_URI,
    #     scope="openid email profile",
    #     key="google",
    # )

    # if result and "token" in result:

    #     token = result["token"]

    #     user_info = requests.get(
    #         "https://www.googleapis.com/oauth2/v1/userinfo",
    #         params={"access_token": token["access_token"]},
    #     ).json()

    #     email = user_info["email"]

    #     st.session_state.zalogowany = True
    #     st.session_state.login = email

    #     st.success(f"Zalogowano przez Google: {email}")

    #     st.rerun()

    st.divider()

    # -------- LOGIN Z GOOGLE SHEETS --------

    uczniowie = pobierz_uczniow()

    login = st.text_input("Login")
    haslo = st.text_input("Hasło", type="password")

    if st.button("Zaloguj"):

        if login in uczniowie and uczniowie[login] == haslo:

            st.session_state.zalogowany = True
            st.session_state.login = login

            st.success("Zalogowano")

            st.rerun()

        else:
            st.error("Błędny login lub hasło")


# -------- PANEL UCZNIA --------

else:

    st.title("Panel ucznia")
    st.write("Zalogowany:", st.session_state.login)

    # -------- FORMULARZ --------

    if not st.session_state.wyslano:

        with st.form("formularz_zadania"):

            st.subheader("Wyślij zadanie")

            imie = st.text_input("Imię")
            nazwisko = st.text_input("Nazwisko")

            email = st.text_input("Email ucznia")

            klasa = st.selectbox(
                "Wybierz klasę",
                ["5TW", "4TM5"]
            )

            tresc = st.text_area("Treść zadania")

            plik = st.file_uploader("Dodaj plik", type=["pdf"])
            with st.expander("Informacja o przetwarzaniu danych (RODO)"):
                    st.write("""
                Administratorem danych jest nauczyciel matematyki.
                Dane (imię, nazwisko, email) są przetwarzane wyłącznie
                w celu sprawdzenia przesłanego zadania.

                Dane nie są przekazywane osobom trzecim i są usuwane
                po zakończeniu sprawdzania zadania.
                """)
            zgoda = st.checkbox(
                "Wyrażam zgodę na przetwarzanie moich danych osobowych "
                "w celu sprawdzenia zadania zgodnie z RODO." )

            submit = st.form_submit_button("Wyślij")

        if submit:
            if not imie:
                st.error("Podaj imię")
            if not nazwisko:
                st.error("Podaj nazwisko")
            if not tresc:
                st.error("Podaj treść zadania")
            if plik is None:
                st.error("Dodaj plik z zadaniem")
            if not zgoda:
                st.error("Wyraź zgodę na przetwarzanie danych osobowych")
            else:
                if not poprawny_email(email):
                    st.error("Podaj poprawny adres email")
                    st.stop()

                files = {
                    "plik": (plik.name, plik.getvalue(), plik.type)
                }

                data = {
                    "uczen": st.session_state.login,
                    "imie": imie,
                    "nazwisko": nazwisko,
                    "klasa": klasa,
                    "tresc": tresc,
                    "email": email
                }
                
                with st.spinner("AI analizuje zadanie..."):

                    response = requests.post(
                        WEBHOOK_URL,
                        files=files,
                        data=data,
                        timeout=60
                    )

                if response.status_code == 200:
                        wynik = response.json()
                        if wynik["status"] == "ok":
                            st.success("Plik zapisany w Google Drive")
                            st.session_state.wyslano = True
                            st.rerun()

                        else:       
                            st.error("Błąd zapisu pliku")

                else:
                    st.error("Błąd komunikacji z serwerem")

    # -------- PO WYSŁANIU --------

    else:

        st.success("Zadanie zostało wysłane")

        st.info("AI sprawdza Twoje rozwiązanie")
    # -------- WYLOGOWANIE --------

    if st.button("Wyloguj"):

        st.session_state.zalogowany = False
        st.session_state.login = None

        st.rerun()