from django.urls import path

from . import views

urlpatterns = [
    path("termos-de-uso/", views.termos_de_uso, name="termos_de_uso"),
    path("privacidade/", views.privacidade, name="privacidade"),
    path("cookies/", views.cookies, name="cookies"),
    path("regras-do-cashback/", views.regras_cashback, name="regras_cashback"),
    path("perguntas-frequentes/", views.faq, name="faq"),
    path("fale-conosco/", views.contato, name="contato"),
]
