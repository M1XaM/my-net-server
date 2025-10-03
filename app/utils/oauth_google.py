from flask import current_app
import urllib.parse
import secrets

from .state_storage import state_storage

def generate_google_oauth_redirect_uri(): # here is all data for info
    # https://developers.google.com/identity/protocols/oauth2/web-server?hl=ru#python_1
    random_state = secrets.token_urlsafe(16)
    state_storage.add(random_state)

    query_params = {  # всё берёться отсюда :
        "client_id": current_app.config['OAUTH_GOOGLE_CLIENT_ID'],
        "redirect_uri": "https://localhost/auth/google",  # eto mi pishem sami v cliente
        "response_type": "code",  # prosto tak delaiu
        "scope": " ".join([  # получить доступ к сервисам с правами-> области действия оаутх
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/calendar",
            "openid",  # esli delaem vhod cherez google() mojno drugie
            "profile",
            "email",
        ]),
        "access_type": "offline",  # refresh token to use disk of user ()
        "state": random_state,  # state is for security
    }
    
    # delaet is dicta query
    query_string = urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    print('dnsajdasd:', f"{base_url}?{query_string}")
    return f"{base_url}?{query_string}"