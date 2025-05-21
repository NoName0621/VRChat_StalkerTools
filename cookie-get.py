import vrchatapi
from vrchatapi.api import authentication_api
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.exceptions import UnauthorizedException, ApiException

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

class VRChatLoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat-Cookie-Get")
        self.root.geometry("400x350")
        self.root.resizable(False, False)

        self.username_var = tb.StringVar()
        self.password_var = tb.StringVar()
        self.code_var = tb.StringVar()

        self.config = None
        self.client = None
        self.auth = None

        self.build_login_ui()

    def build_login_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        tb.Label(self.root, text="VRChatユーザー名、またはEmail", font=("Arial", 12)).pack(pady=(20, 5))
        tb.Entry(self.root, textvariable=self.username_var, width=30).pack()

        tb.Label(self.root, text="パスワード", font=("Arial", 12)).pack(pady=(10, 5))
        tb.Entry(self.root, textvariable=self.password_var, show="*", width=30).pack()

        tb.Button(self.root, text="ログイン", bootstyle="success", command=self.try_login).pack(pady=20)


    def build_2fa_ui(self, method="2FA"):
        for widget in self.root.winfo_children():
            widget.destroy()

        label_text = "📧 Email 2FAコード" if method == "email" else "🔐 2FAコード"
        tb.Label(self.root, text=label_text, font=("Arial", 12)).pack(pady=(40, 5))
        tb.Entry(self.root, textvariable=self.code_var, width=30).pack()

        tb.Button(self.root, text="認証", bootstyle="info", command=lambda: self.verify_code(method)).pack(pady=20)

    def try_login(self):
        username = self.username_var.get()
        password = self.password_var.get()

        if not username or not password:
            messagebox.showerror("エラー", "ユーザー名とパスワードを入力してください。")
            return

        self.config = vrchatapi.Configuration(username=username, password=password)
        self.client = vrchatapi.ApiClient(self.config)
        self.client.user_agent = "VRChatAPI-Python-Client/1.19.2/python"
        self.auth = authentication_api.AuthenticationApi(self.client)

        try:
            self.auth.get_current_user()
            self.save_cookie()
        except UnauthorizedException as e:
            if e.status == 200:
                self.build_2fa_ui("email")
            elif "2 Factor Authentication" in str(e.reason):
                self.build_2fa_ui("2FA")
            else:
                messagebox.showerror("ログイン失敗", "ユーザー名またはパスワードが違います。")
        except ApiException as e:
            messagebox.showerror("APIエラー", str(e))

    def verify_code(self, method):
        code = self.code_var.get()
        try:
            if method == "2FA":
                self.auth.verify2_fa(TwoFactorAuthCode(code))
            else:
                self.auth.verify2_fa_email_code(TwoFactorEmailCode(code))

            self.auth.get_current_user()
            self.save_cookie()
        except ApiException:
            messagebox.showerror("認証失敗", "コードが正しくありません。")

    def save_cookie(self):
        cookies = self.client.rest_client.cookie_jar
        if not cookies:
            messagebox.showerror("エラー", "クッキー取得に失敗しました。")
            return

        with open("cookie.txt", "w") as f:
            for cookie in cookies:
                f.write(f"{cookie.name}={cookie.value}; domain={cookie.domain}; path={cookie.path}\n")

        messagebox.showinfo("成功", "✅ cookie.txtに保存されました")
        self.root.quit()


if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    app = VRChatLoginApp(root)
    root.mainloop()
