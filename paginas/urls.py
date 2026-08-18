from django.urls import path

from . import views

urlpatterns = [
    path("termos-de-uso/", views.termos_de_uso, name="termos_de_uso"),
    path("privacidade/", views.privacidade, name="privacidade"),
    path("cookies/", views.cookies, name="cookies"),
    path("regras-do-cashback/", views.regras_cashback, name="regras_cashback"),
    path("perguntas-frequentes/", views.faq, name="faq"),
    path("fale-conosco/", views.contato, name="contato"),
    path("cashback-na-shopee-vale-a-pena/", views.cashback_vale_a_pena, name="cashback_vale_a_pena"),
    path("cash-b-e-confiavel/", views.e_confiavel, name="e_confiavel"),
    path(
        "como-saber-se-site-de-cashback-e-confiavel/",
        views.checklist_cashback_confiavel,
        name="checklist_cashback_confiavel",
    ),
]
