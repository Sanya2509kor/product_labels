from django.urls import path
from . import views
from . import api_views


urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('create-establishment/', views.create_establishment, name='create_establishment'),
    path('join-establishment/', views.join_establishment, name='join_establishment'),
    path('establishment/<int:establishment_id>/members/', views.establishment_members, name='establishment_members'),
    path('establishment/<int:establishment_id>/employees/', views.employee_list, name='employee_list'),
    path('establishment/<int:establishment_id>/employees/add/', views.add_employee, name='add_employee'),
    path('employees/<int:employee_id>/edit/', views.edit_employee, name='edit_employee'),
    path('employees/<int:employee_id>/delete/', views.delete_employee, name='delete_employee'),
    path('employees/<int:employee_id>/toggle/', views.toggle_employee, name='toggle_employee'),
    path('label/<int:label_id>/print/', views.print_label, name='print_label'),
    path('label/<int:label_id>/edit/', views.edit_label, name='edit_label'),
    path('label/<int:label_id>/delete/', views.delete_label, name='delete_label'),
    path('cart/add/<int:label_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:label_id>/ajax/', views.add_to_cart_ajax, name='add_to_cart_ajax'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/print/', views.print_cart, name='print_cart'),
    path('employee-session/start/<int:employee_id>/', views.start_employee_session, name='start_employee_session'),
    path('employee-session/stop/', views.stop_employee_session, name='stop_employee_session'),
    path('establishment/<int:establishment_id>/employee-switch/', views.quick_employee_switch, name='quick_employee_switch'),
    path('establishment/<int:establishment_id>/categories/', views.category_list, name='category_list'),
    path('establishment/<int:establishment_id>/categories/add/', views.add_category, name='add_category'),
    path('categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    path('categories/<int:category_id>/toggle/', views.toggle_category, name='toggle_category'),
    path('expired-products/', views.expired_products, name='expired_products'),
    path('expired-products/delete/<int:product_id>/', views.delete_expired_product, name='delete_expired_product'),
    path('expired-products/delete-all/', views.delete_all_expired, name='delete_all_expired'),
    path('expired-products/delete-category/<int:category_id>/', views.delete_expired_by_category, name='delete_expired_by_category'),
    path('expired-products/reprint/', views.reprint_expired_products, name='reprint_expired_products'),
    path('employee-session/start/<int:employee_id>/ajax/', views.start_employee_session_ajax, name='start_employee_session_ajax'),
    path('employee-session/stop/ajax/', views.stop_employee_session_ajax, name='stop_employee_session_ajax'),



    # API для мобильного приложения
    path('api/me/', api_views.api_me, name='api_me'),
    path('api/establishments/<int:establishment_id>/labels/', api_views.api_labels, name='api_labels'),
    path('api/establishments/<int:establishment_id>/categories/', api_views.api_categories, name='api_categories'),
    path('api/establishments/<int:establishment_id>/employees/', api_views.api_employees, name='api_employees'),
    path('api/establishments/<int:establishment_id>/cart/', api_views.api_cart, name='api_cart'),
    path('api/establishments/<int:establishment_id>/labels/create/',
     api_views.api_label_create, name='api_label_create'),

    path('api-tester/', views.api_tester, name='api_tester'),
    path('api-key/', views.api_key_page, name='api_key_page'),
    path('api-key/regenerate/', views.api_key_regenerate, name='api_key_regenerate'),
    path('app-connect/', views.app_connect, name='app_connect'),

    # Сотрудники
    path('api/establishments/<int:establishment_id>/employees/create/',
        api_views.api_employee_create, name='api_employee_create'),
    path('api/establishments/<int:establishment_id>/employees/<int:employee_id>/update/',
        api_views.api_employee_update, name='api_employee_update'),
    path('api/establishments/<int:establishment_id>/employees/<int:employee_id>/delete/',
        api_views.api_employee_delete, name='api_employee_delete'),
    path('api/establishments/<int:establishment_id>/employees/<int:employee_id>/toggle/',
        api_views.api_employee_toggle, name='api_employee_toggle'),

    # Категории
    path('api/establishments/<int:establishment_id>/categories/create/',
        api_views.api_category_create, name='api_category_create'),
    path('api/establishments/<int:establishment_id>/categories/<int:category_id>/update/',
        api_views.api_category_update, name='api_category_update'),
    path('api/establishments/<int:establishment_id>/categories/<int:category_id>/delete/',
        api_views.api_category_delete, name='api_category_delete'),
    path('api/establishments/<int:establishment_id>/categories/<int:category_id>/toggle/',
        api_views.api_category_toggle, name='api_category_toggle'),

    path('print/<int:establishment_id>/', views.print_page, name='print_page'),
    path('print/job/create/<int:label_id>/', views.print_create_job, name='print_create_job'),
    path('print/<int:establishment_id>/cart/', views.print_create_cart, name='print_create_cart'),
    path('print/job/<int:job_id>/status/', views.print_job_status, name='print_job_status'),  # ← добавить

    path('api/establishments/<int:establishment_id>/print/pending/',
        api_views.api_print_pending, name='api_print_pending'),
    path('api/print/<int:job_id>/complete/',
        api_views.api_print_complete, name='api_print_complete'),
]