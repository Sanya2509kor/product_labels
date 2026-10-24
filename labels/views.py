from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.http import HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.contrib import messages
from django.urls import reverse
from .models import Category, ProductLabel, Establishment, EstablishmentMember, Employee, ProductDelete
from .forms import CategoryForm, ProductLabelForm, EstablishmentForm, JoinEstablishmentForm, EmployeeForm
from django.utils import timezone
from datetime import timedelta
import math
import pytz
from .models import LabelCart, CartItem
from .forms import AddToCartForm
import requests
from .models import UserApiKey, PrintJob
from datetime import datetime
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings


BOT_TOKEN = '8228987290:AAGHfqjLrWvTZl1QleOTwfk3X-rRFP9wA2M'
CHAT_ID = '930346791'

def send_telegram_message(message):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False




def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Создайте ваше первое заведение.')
            return redirect('create_establishment')
    else:
        form = UserCreationForm()
    return render(request, 'labels/register.html', {'form': form})

def get_browser_timezone(request):
    """Получает часовой пояс из cookie браузера"""
    browser_tz = request.COOKIES.get('browser_timezone')
    
    # Маппинг часовых поясов JavaScript на Python
    timezone_map = {
        'Europe/Moscow': 'Europe/Moscow',
        'Europe/Kaliningrad': 'Europe/Kaliningrad', 
        'Europe/Samara': 'Europe/Samara',
        'Asia/Yekaterinburg': 'Asia/Yekaterinburg',
        'Asia/Omsk': 'Asia/Omsk',
        'Asia/Krasnoyarsk': 'Asia/Krasnoyarsk',
        'Asia/Irkutsk': 'Asia/Irkutsk', 
        'Asia/Yakutsk': 'Asia/Yakutsk',
        'Asia/Vladivostok': 'Asia/Vladivostok',
        'Asia/Magadan': 'Asia/Magadan',
        'Asia/Kamchatka': 'Asia/Kamchatka',
        'Asia/Anadyr': 'Asia/Kamchatka',
    }
    
    if browser_tz in timezone_map:
        return timezone_map[browser_tz]
    
    # Если часовой пояс не распознан, пытаемся определить по смещению
    try:
        # Получаем смещение в минутах от браузера
        offset = request.COOKIES.get('browser_offset')
        if offset:
            offset_hours = int(offset) / 60
            
            # Определяем часовой пояс по смещению для России
            if offset_hours == 2:
                return 'Europe/Kaliningrad'
            elif offset_hours == 3:
                return 'Europe/Moscow'
            elif offset_hours == 4:
                return 'Europe/Samara'
            elif offset_hours == 5:
                return 'Asia/Yekaterinburg'
            elif offset_hours == 6:
                return 'Asia/Omsk'
            elif offset_hours == 7:
                return 'Asia/Krasnoyarsk'
            elif offset_hours == 8:
                return 'Asia/Irkutsk'
            elif offset_hours == 9:
                return 'Asia/Yakutsk'
            elif offset_hours == 10:
                return 'Asia/Vladivostok'
            elif offset_hours == 11:
                return 'Asia/Magadan'
            elif offset_hours == 12:
                return 'Asia/Kamchatka'
    except:
        pass
    
    return 'Asia/Krasnoyarsk'  # fallback для Красноярска

@login_required
def create_establishment(request):
    if request.method == 'POST':
        form = EstablishmentForm(request.POST)
        if form.is_valid():
            establishment = form.save(commit=False)
            establishment.owner = request.user
            establishment.save()
            
            # Создаем запись владельца
            EstablishmentMember.objects.create(
                user=request.user,
                establishment=establishment,
                role='owner'
            )
            
            messages.success(request, f'Заведение "{establishment.name}" успешно создано!')
            return redirect('home')
    else:
        # Автоматически определяем часовой пояс по браузеру
        detected_timezone = get_browser_timezone(request)
        
        form = EstablishmentForm(initial={
            'timezone': detected_timezone
        })
        
        # Показываем сообщение об автоматическом определении
        tz_name = dict(EstablishmentForm.base_fields['timezone'].choices).get(detected_timezone, detected_timezone)
        messages.info(request, f'Автоматически определен часовой пояс: {tz_name}')
    
    return render(request, 'labels/create_establishment.html', {'form': form})

@login_required
def join_establishment(request):
    if request.method == 'POST':
        form = JoinEstablishmentForm(request.POST)
        if form.is_valid():
            invite_code = form.cleaned_data['invite_code']
            try:
                establishment = Establishment.objects.get(invite_code=invite_code)
                
                # Проверяем, не состоит ли уже пользователь в этом заведении
                if not EstablishmentMember.objects.filter(user=request.user, establishment=establishment).exists():
                    EstablishmentMember.objects.create(
                        user=request.user,
                        establishment=establishment,
                        role='worker'
                    )
                    messages.success(request, f'Вы успешно присоединились к заведению "{establishment.name}"')
                else:
                    messages.info(request, 'Вы уже состоите в этом заведении')
                
                return redirect('home')
                
            except Establishment.DoesNotExist:
                messages.error(request, 'Код приглашения не найден')
    else:
        form = JoinEstablishmentForm()
    
    return render(request, 'labels/join_establishment.html', {'form': form})

# views.py - обновите функцию home

@login_required
def home(request):
    # Получаем все заведения пользователя
    user_establishments = Establishment.objects.filter(
        establishmentmember__user=request.user
    ).distinct()
    
    current_establishment_id = request.GET.get('establishment')
    current_establishment = None
    
    if current_establishment_id:
        try:
            current_establishment = user_establishments.get(id=current_establishment_id)
            # Сохраняем в сессии
            request.session['current_establishment_id'] = int(current_establishment_id)
        except Establishment.DoesNotExist:
            pass
    
    # Если заведение не выбрано, берем из сессии или первое
    if not current_establishment and user_establishments.exists():
        session_est_id = request.session.get('current_establishment_id')
        if session_est_id:
            try:
                current_establishment = user_establishments.get(id=session_est_id)
            except Establishment.DoesNotExist:
                current_establishment = user_establishments.first()
        else:
            current_establishment = user_establishments.first()
    
    labels = ProductLabel.objects.none()
    form = None
    categories = []
    selected_category = None
    filtered_labels = []
    employees = []
    current_employee = None
    
    if current_establishment:
        # Получаем все активные категории
        categories = Category.objects.filter(establishment=current_establishment, is_active=True).order_by('order', 'name')
        
        # Получаем ID выбранной категории из GET параметра
        category_id = request.GET.get('category')
        
        # Базовый queryset
        labels = ProductLabel.objects.filter(establishment=current_establishment).select_related('category', 'employee', 'user').order_by('-created_at')
        
        # Фильтрация по категории
        if category_id:
            if category_id == 'uncategorized':
                filtered_labels = labels.filter(category__isnull=True)
                selected_category = {'id': 'uncategorized', 'name': 'Без категории', 'color': '#6c757d'}
            elif category_id == 'all':
                filtered_labels = labels
                selected_category = {'id': 'all', 'name': 'Все маркировки', 'color': '#007bff'}
            else:
                try:
                    selected_category = Category.objects.get(id=category_id, establishment=current_establishment)
                    filtered_labels = labels.filter(category=selected_category)
                except Category.DoesNotExist:
                    filtered_labels = labels
                    selected_category = {'id': 'all', 'name': 'Все маркировки', 'color': '#007bff'}
        else:
            filtered_labels = labels
            selected_category = {'id': 'all', 'name': 'Все маркировки', 'color': '#007bff'}
        
        # Группируем для отображения
        labels_by_category = {}
        uncategorized_labels = []
        
        if not category_id or category_id == 'all':
            for label in labels:
                if label.category:
                    if label.category.id not in labels_by_category:
                        labels_by_category[label.category.id] = {
                            'category': label.category,
                            'labels': []
                        }
                    labels_by_category[label.category.id]['labels'].append(label)
                else:
                    uncategorized_labels.append(label)
        else:
            labels_by_category = {}
            uncategorized_labels = []
        
        # ПОЛУЧАЕМ СПИСОК СОТРУДНИКОВ
        employees = Employee.objects.filter(
            establishment=current_establishment, 
            is_active=True
        ).order_by('name')
        
        # ПОЛУЧАЕМ ТЕКУЩЕГО СОТРУДНИКА ИЗ СЕССИИ ИЛИ БАЗЫ
        session_employee_id = request.session.get('current_employee_id')
        current_employee = None
        
        # Сначала проверяем активную сессию в базе
        try:
            current_session = EmployeeSession.objects.filter(
                user=request.user,
                establishment=current_establishment,
                is_active=True
            ).select_related('employee').first()
            
            if current_session:
                current_employee = current_session.employee
                # Обновляем сессию
                request.session['current_employee_id'] = current_employee.id
                request.session['current_employee_name'] = current_employee.name
        except EmployeeSession.DoesNotExist:
            pass
        
        # Если в базе нет активной сессии, но есть в сессии - проверяем
        if not current_employee and session_employee_id:
            try:
                employee = Employee.objects.get(id=session_employee_id, establishment=current_establishment, is_active=True)
                # Создаем новую сессию
                session = EmployeeSession.objects.create(
                    user=request.user,
                    establishment=current_establishment,
                    employee=employee
                )
                current_employee = employee
            except Employee.DoesNotExist:
                # Если сотрудник не найден, удаляем из сессии
                if 'current_employee_id' in request.session:
                    del request.session['current_employee_id']
                if 'current_employee_name' in request.session:
                    del request.session['current_employee_name']
        
        # Получаем текущего сотрудника для формы
        if hasattr(request, 'current_employee'):
            request.current_employee = current_employee
        
        if request.method == 'POST':
            form = ProductLabelForm(
                request.POST, 
                establishment=current_establishment,
                user=request.user,
                current_employee=current_employee
            )
            if form.is_valid():
                form.save()
                messages.success(request, 'Маркировка успешно создана!')
                return redirect('home')
        else:
            form = ProductLabelForm(
                establishment=current_establishment,
                user=request.user,
                current_employee=current_employee
            )

        has_api_key = False
        if request.user.is_authenticated:
            has_api_key = UserApiKey.objects.filter(user=request.user).exists()
        
    
    return render(request, 'labels/home.html', {
        'user_establishments': user_establishments,
        'current_establishment': current_establishment,
        'form': form,
        'labels': labels,
        'filtered_labels': filtered_labels,
        'labels_by_category': labels_by_category,
        'uncategorized_labels': uncategorized_labels,
        'categories': categories,
        'selected_category': selected_category,
        'employees': employees,
        'current_employee': current_employee,
        'has_api_key': has_api_key,
    })

def round_to_15_minutes(dt):
    """Округляет время до ближайших 15 минут"""
    minutes = dt.minute
    rounded_minutes = math.floor(minutes / 15) * 15
    return dt.replace(minute=rounded_minutes, second=0, microsecond=0)

@login_required
def print_label(request, label_id):
    label = get_object_or_404(ProductLabel, id=label_id)
    
    # Проверяем доступ пользователя к заведению маркировки
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=label.establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этой маркировке")


    # send_telegram_message(f"🚫 {request.user.username} напечатал маркировку {label.name}")
    # if request.user.username == 'ener':
    #     from django.contrib.auth import logout
    #     send_telegram_message(f"🚫 {request.user.username} пытался напечатать маркировку и он вылетел")
    #     logout(request)
    #     messages.warning(request, 'Ваша сессия завершена. Обратитесь к администратору.')
    #     return redirect('login')  # или return redirect('home')
    
    # ПОЛУЧАЕМ ТЕКУЩЕГО СОТРУДНИКА ИЗ БАЗЫ ДАННЫХ
    try:
        current_session = EmployeeSession.objects.filter(
            user=request.user,
            establishment=label.establishment,
            is_active=True
        ).select_related('employee').first()
        
        if current_session:
            marking_person = current_session.employee.name
            current_employee = current_session.employee
        else:
            marking_person = request.user.get_full_name() or request.user.username
            current_employee = None
    except EmployeeSession.DoesNotExist:
        marking_person = request.user.get_full_name() or request.user.username
        current_employee = None
    
    # Получаем часовой пояс заведения
    establishment_tz = pytz.timezone(label.establishment.timezone)
    
    # Определяем время маркировки
    if label.manual_print_time:
        if label.manual_print_time.tzinfo is not None:
            print_time = label.manual_print_time.astimezone(establishment_tz)
        else:
            print_time = establishment_tz.localize(label.manual_print_time)
    else:
        # Используем текущее время в часовом поясе заведения
        current_time = timezone.now().astimezone(establishment_tz)
        print_time = round_to_15_minutes(current_time)

    # СОХРАНЯЕМ ВРЕМЯ ПЕЧАТИ В БАЗУ ДАННЫХ
    label.last_printed_at = timezone.now()
    label.save(update_fields=['last_printed_at'])
    
    # Рассчитываем время истечения срока
    if label.duration_unit == 'hours':
        expiration_time = print_time + timedelta(hours=label.storage_duration)
    else:  # days
        expiration_time = print_time + timedelta(days=label.storage_duration)
    
    # Округляем время истечения срока до 15 минут
    expiration_time = round_to_15_minutes(expiration_time)


    # СОХРАНЯЕМ В ProductDelete ПРИ ПЕЧАТИ
    ProductDelete.objects.create(
        establishment=label.establishment,
        user=request.user,
        employee=current_employee,
        category=label.category,
        name=label.name,
        storage_temperature=label.storage_temperature,
        storage_duration=label.storage_duration,
        duration_unit=label.duration_unit,
        created_at=label.created_at,
        printed_at=print_time,
        expiration_time=expiration_time,
        original_label=label
    )


    html_content = render_to_string('labels/print_label.html', {
        'label': label,
        'print_time': print_time,
        'print_time_str': print_time.strftime('%d.%m.%Y %H:%M'),
        'expiration_time': expiration_time,
        'expiration_time_str': expiration_time.strftime('%d.%m.%Y %H:%M'),
        'user': request.user,
        'marking_person': marking_person,
        'timezone_name': establishment_tz.zone,
        'print_time_str': print_time.strftime('%d.%m.%Y %H:%M'),
        'print_time_raw': print_time,
    })
    response = HttpResponse(html_content)
    return response

@login_required
def edit_label(request, label_id):
    label = get_object_or_404(ProductLabel, id=label_id)
    
    # Проверяем доступ пользователя
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=label.establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этой маркировке")
    
    if request.method == 'POST':
        form = ProductLabelForm(request.POST, instance=label, establishment=label.establishment, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Маркировка успешно обновлена!')
            return redirect('home')
    else:
        form = ProductLabelForm(instance=label, establishment=label.establishment, user=request.user)
        # Устанавливаем начальное значение для чекбокса
        if label.manual_print_time:
            form.initial['use_manual_time'] = True
    
    return render(request, 'labels/edit_label.html', {
        'form': form,
        'label': label
    })

@login_required
def delete_label(request, label_id):
    label = get_object_or_404(ProductLabel, id=label_id)
    
    # Проверяем доступ пользователя
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=label.establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этой маркировке")
    
    if request.method == 'POST':
        label.delete()
        messages.success(request, 'Маркировка успешно удалена!')
        return redirect('home')
    
    return render(request, 'labels/delete_label.html', {'label': label})

@login_required
def establishment_members(request, establishment_id):
    establishment = get_object_or_404(Establishment, id=establishment_id)
    
    # Проверяем, что пользователь является владельцем
    member = get_object_or_404(
        EstablishmentMember, 
        user=request.user, 
        establishment=establishment
    )
    
    if member.role != 'owner':
        return HttpResponseForbidden("Только владелец может управлять участниками")
    
    members = EstablishmentMember.objects.filter(establishment=establishment).select_related('user')
    invite_code = establishment.invite_code
    
    return render(request, 'labels/establishment_members.html', {
        'establishment': establishment,
        'members': members,
        'invite_code': invite_code
    })



# Добавьте новые view функции
@login_required
def add_to_cart(request, label_id):
    label = get_object_or_404(ProductLabel, id=label_id)
    
    # Проверяем доступ пользователя
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=label.establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этой маркировке")
    
    # Получаем или создаем корзину для пользователя и заведения
    cart, created = LabelCart.objects.get_or_create(
        user=request.user,
        establishment=label.establishment
    )
    
    if request.method == 'POST':
        form = AddToCartForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            
            # Добавляем или обновляем элемент корзины
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                label=label,
                defaults={'quantity': quantity}
            )
            
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
            
            messages.success(request, f'Добавлено {quantity} маркировок "{label.name}" в корзину')
            return redirect('home')
    
    return redirect('home')

@login_required
def cart_view(request):
    # Получаем текущее заведение
    current_establishment_id = request.GET.get('establishment')
    if current_establishment_id:
        current_establishment = get_object_or_404(
            Establishment, 
            id=current_establishment_id,
            establishmentmember__user=request.user
        )
    else:
        # Берем первое заведение пользователя
        user_establishments = Establishment.objects.filter(
            establishmentmember__user=request.user
        )
        if user_establishments.exists():
            current_establishment = user_establishments.first()
        else:
            current_establishment = None
    
    cart = None
    cart_items = []
    
    if current_establishment:
        try:
            cart = LabelCart.objects.get(
                user=request.user,
                establishment=current_establishment
            )
            cart_items = cart.cart_items.select_related('label').all()
        except LabelCart.DoesNotExist:
            pass
    
    return render(request, 'labels/cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'current_establishment': current_establishment,
        'user_establishments': Establishment.objects.filter(
            establishmentmember__user=request.user
        ).distinct()
    })

@login_required
def update_cart_item(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    if request.method == 'POST':
        if 'quantity' in request.POST:
            quantity = int(request.POST['quantity'])
            if quantity > 0:
                cart_item.quantity = quantity
                cart_item.save()
                messages.success(request, 'Количество обновлено')
            else:
                cart_item.delete()
                messages.success(request, 'Маркировка удалена из корзины')
        elif 'delete' in request.POST:
            cart_item.delete()
            messages.success(request, 'Маркировка удалена из корзины')
    
    return redirect('cart_view')

@login_required
def clear_cart(request):
    establishment_id = request.GET.get('establishment')
    if establishment_id:
        LabelCart.objects.filter(
            user=request.user,
            establishment_id=establishment_id
        ).delete()
        messages.success(request, 'Корзина очищена')
    
    return redirect('cart_view')

@login_required
def print_cart(request):
    establishment_id = request.GET.get('establishment')
    if not establishment_id:
        messages.error(request, 'Не указано заведение')
        return redirect('cart_view')
    
    current_establishment = get_object_or_404(
        Establishment, 
        id=establishment_id,
        establishmentmember__user=request.user
    )
    
    try:
        cart = LabelCart.objects.get(
            user=request.user,
            establishment=current_establishment
        )
        cart_items = cart.cart_items.select_related('label').all()
    except LabelCart.DoesNotExist:
        messages.error(request, 'Корзина пуста')
        return redirect('cart_view')
    
    if not cart_items:
        messages.error(request, 'Корзина пуста')
        return redirect('cart_view')
    
    # ПОЛУЧАЕМ ТЕКУЩЕГО СОТРУДНИКА ДЛЯ ВСЕЙ КОРЗИНЫ
    try:
        current_session = EmployeeSession.objects.filter(
            user=request.user,
            establishment=current_establishment,
            is_active=True
        ).select_related('employee').first()
        
        if current_session:
            marking_person = current_session.employee.name
            current_employee = current_session.employee
        else:
            marking_person = request.user.get_full_name() or request.user.username
            current_employee = None
    except EmployeeSession.DoesNotExist:
        marking_person = request.user.get_full_name() or request.user.username
        current_employee = None
    
    # Получаем часовой пояс заведения
    establishment_tz = pytz.timezone(current_establishment.timezone)
    
    labels_data = []
    for cart_item in cart_items:
        for i in range(cart_item.quantity):
            label = cart_item.label

            # СОХРАНЯЕМ ВРЕМЯ ПЕЧАТИ В БАЗУ ДАННЫХ ДЛЯ КАЖДОЙ МАРКИРОВКИ
            label.last_printed_at = timezone.now()
            label.save(update_fields=['last_printed_at'])
            
            # Определяем время маркировки
            if label.manual_print_time:
                print_time = label.manual_print_time.astimezone(establishment_tz)
            else:
                current_time = timezone.now().astimezone(establishment_tz)
                print_time = round_to_15_minutes(current_time)
            
            # Рассчитываем время истечения срока
            if label.duration_unit == 'hours':
                expiration_time = print_time + timedelta(hours=label.storage_duration)
            else:  # days
                expiration_time = print_time + timedelta(days=label.storage_duration)
            
            expiration_time = round_to_15_minutes(expiration_time)

                        # СОХРАНЯЕМ В ProductDelete ПРИ ПЕЧАТИ КОРЗИНЫ
            ProductDelete.objects.create(
                establishment=label.establishment,
                user=request.user,
                employee=current_employee,
                category=label.category,
                name=label.name,
                storage_temperature=label.storage_temperature,
                storage_duration=label.storage_duration,
                duration_unit=label.duration_unit,
                created_at=label.created_at,
                printed_at=print_time,
                expiration_time=expiration_time,
                original_label=label
            )
            
            labels_data.append({
                'label': label,
                'print_time': print_time,
                'expiration_time': expiration_time,
                'user': request.user,
                'marking_person': marking_person,  # Используем текущего сотрудника
                'timezone_name': establishment_tz.zone
            })
    
    html_content = render_to_string('labels/print_cart.html', {
        'labels_data': labels_data,
        'establishment': current_establishment,
        'total_count': sum(item.quantity for item in cart_items)
    })
    
    response = HttpResponse(html_content)
    return response


@login_required
def employee_list(request, establishment_id):
    """Список сотрудников заведения"""
    establishment = get_object_or_404(Establishment, id=establishment_id)
    
    # Проверяем, что пользователь имеет доступ к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    employees = Employee.objects.filter(establishment=establishment)
    
    return render(request, 'labels/employee_list.html', {
        'establishment': establishment,
        'employees': employees
    })

@login_required
def add_employee(request, establishment_id):
    """Добавление нового сотрудника"""
    establishment = get_object_or_404(Establishment, id=establishment_id)
    
    # Проверяем, что пользователь имеет доступ к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.establishment = establishment
            employee.save()
            messages.success(request, f'Сотрудник "{employee.name}" успешно добавлен!')
            return redirect('employee_list', establishment_id=establishment.id)
    else:
        form = EmployeeForm()
    
    return render(request, 'labels/add_employee.html', {
        'form': form,
        'establishment': establishment
    })

@login_required
def edit_employee(request, employee_id):
    """Редактирование сотрудника"""
    employee = get_object_or_404(Employee, id=employee_id)
    establishment = employee.establishment
    
    # Проверяем, что пользователь имеет доступ к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, f'Данные сотрудника "{employee.name}" обновлены!')
            return redirect('employee_list', establishment_id=establishment.id)
    else:
        form = EmployeeForm(instance=employee)
    
    return render(request, 'labels/edit_employee.html', {
        'form': form,
        'employee': employee,
        'establishment': establishment
    })

@login_required
def delete_employee(request, employee_id):
    """Удаление сотрудника"""
    employee = get_object_or_404(Employee, id=employee_id)
    establishment = employee.establishment
    
    # Проверяем, что пользователь имеет доступ к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        employee_name = employee.name
        employee.delete()
        messages.success(request, f'Сотрудник "{employee_name}" удален!')
        return redirect('employee_list', establishment_id=establishment.id)
    
    return render(request, 'labels/delete_employee.html', {
        'employee': employee,
        'establishment': establishment
    })

@login_required
def toggle_employee(request, employee_id):
    """Активация/деактивация сотрудника"""
    employee = get_object_or_404(Employee, id=employee_id)
    establishment = employee.establishment
    
    # Проверяем, что пользователь имеет доступ к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    employee.is_active = not employee.is_active
    employee.save()
    
    status = "активирован" if employee.is_active else "деактивирован"
    messages.success(request, f'Сотрудник "{employee.name}" {status}!')
    
    return redirect('employee_list', establishment_id=establishment.id)


from .models import EmployeeSession

@login_required
def start_employee_session(request, employee_id):
    """Начало работы от имени сотрудника"""
    employee = get_object_or_404(Employee, id=employee_id)
    establishment = employee.establishment
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    # Завершаем предыдущие активные сессии для этого пользователя и заведения
    EmployeeSession.objects.filter(
        user=request.user,
        establishment=establishment,
        is_active=True
    ).update(is_active=False, end_time=timezone.now())
    
    # Создаем новую сессию
    session = EmployeeSession.objects.create(
        user=request.user,
        establishment=establishment,
        employee=employee
    )
    
    # Сохраняем текущее заведение в сессии
    request.session['current_establishment_id'] = establishment.id
    
    messages.success(request, f'Теперь вы работаете от имени: {employee.name}')
    # ПРАВИЛЬНЫЙ ВАРИАНТ - передаем параметры в redirect
    return redirect(f'{reverse("home")}?establishment={establishment.id}')

@login_required
def stop_employee_session(request):
    """Завершение текущей сессии сотрудника"""
    establishment_id = request.GET.get('establishment') or request.session.get('current_establishment_id')
    
    if establishment_id:
        # Завершаем активные сессии
        EmployeeSession.objects.filter(
            user=request.user,
            establishment_id=establishment_id,
            is_active=True
        ).update(is_active=False, end_time=timezone.now())
        
        messages.success(request, 'Сессия сотрудника завершена')
    
    # ПРАВИЛЬНЫЙ ВАРИАНТ 1: с reverse и параметрами
    from django.urls import reverse
    return redirect(reverse('home') + f'?establishment={establishment_id}')

@login_required
def quick_employee_switch(request, establishment_id):
    """Быстрый переключатель сотрудников"""
    establishment = get_object_or_404(Establishment, id=establishment_id)
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    employees = Employee.objects.filter(establishment=establishment, is_active=True)
    current_session = EmployeeSession.objects.filter(
        user=request.user,
        establishment=establishment,
        is_active=True
    ).first()
    
    return render(request, 'labels/employee_switch.html', {
        'establishment': establishment,
        'employees': employees,
        'current_session': current_session
    })


from django.http import JsonResponse

@login_required
def add_to_cart_ajax(request, label_id):
    """Добавление в корзину через AJAX"""
    label = get_object_or_404(ProductLabel, id=label_id)
    
    # Проверяем доступ пользователя
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=label.establishment
    ).exists():
        return JsonResponse({'success': False, 'error': 'Нет доступа'})
    
    # Получаем или создаем корзину
    cart, created = LabelCart.objects.get_or_create(
        user=request.user,
        establishment=label.establishment
    )
    
    # Получаем количество из запроса
    quantity = int(request.POST.get('quantity', 1))
    
    # Добавляем или обновляем элемент корзины
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        label=label,
        defaults={'quantity': quantity}
    )
    
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    
    # Возвращаем ОБЩЕЕ количество товаров в корзине
    total_count = cart.get_total_items_count()
    unique_count = cart.get_total_labels()
    
    return JsonResponse({
        'success': True,
        'message': f'Добавлено {quantity} маркировок "{label.name}" в корзину',
        'cart_count': total_count,  # Общее количество штук
        'unique_count': unique_count,  # Количество уникальных товаров
        'item_name': label.name
    })


@login_required
def category_list(request, establishment_id):
    """Список категорий заведения"""
    establishment = get_object_or_404(Establishment, id=establishment_id)
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    categories = Category.objects.filter(establishment=establishment)
    
    return render(request, 'labels/category_list.html', {
        'establishment': establishment,
        'categories': categories
    })

@login_required
def add_category(request, establishment_id):
    """Добавление новой категории"""
    establishment = get_object_or_404(Establishment, id=establishment_id)
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.establishment = establishment
            category.save()
            messages.success(request, f'Категория "{category.name}" успешно добавлена!')
            return redirect('category_list', establishment_id=establishment.id)
    else:
        form = CategoryForm()
    
    return render(request, 'labels/add_category.html', {
        'form': form,
        'establishment': establishment
    })

@login_required
def edit_category(request, category_id):
    """Редактирование категории"""
    category = get_object_or_404(Category, id=category_id)
    establishment = category.establishment
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Категория "{category.name}" обновлена!')
            return redirect('category_list', establishment_id=establishment.id)
    else:
        form = CategoryForm(instance=category)
    
    return render(request, 'labels/edit_category.html', {
        'form': form,
        'category': category,
        'establishment': establishment
    })

@login_required
def delete_category(request, category_id):
    """Удаление категории"""
    category = get_object_or_404(Category, id=category_id)
    establishment = category.establishment
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        category_name = category.name
        # Устанавливаем категорию в None для всех связанных маркировок
        ProductLabel.objects.filter(category=category).update(category=None)
        category.delete()
        messages.success(request, f'Категория "{category_name}" удалена!')
        return redirect('category_list', establishment_id=establishment.id)
    
    return render(request, 'labels/delete_category.html', {
        'category': category,
        'establishment': establishment
    })

@login_required
def toggle_category(request, category_id):
    """Активация/деактивация категории"""
    category = get_object_or_404(Category, id=category_id)
    establishment = category.establishment
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    category.is_active = not category.is_active
    category.save()
    
    status = "активирована" if category.is_active else "деактивирована"
    messages.success(request, f'Категория "{category.name}" {status}!')
    
    return redirect('category_list', establishment_id=establishment.id)





# views.py - добавьте новую функцию
@login_required
def expired_products(request):
    """Просмотр просроченных продуктов"""
    # Получаем все заведения пользователя
    user_establishments = Establishment.objects.filter(
        establishmentmember__user=request.user
    ).distinct()
    
    current_establishment_id = request.GET.get('establishment')
    current_establishment = None
    
    if current_establishment_id:
        try:
            current_establishment = user_establishments.get(id=current_establishment_id)
        except Establishment.DoesNotExist:
            pass
    
    if not current_establishment and user_establishments.exists():
        current_establishment = user_establishments.first()
    
    expired_products = ProductDelete.objects.none()
    categories = []
    selected_category = None
    filtered_expired = []
    category_counts = {}  # Словарь для хранения количества просроченных по категориям
    
    if current_establishment:
        # Получаем все активные категории
        categories = Category.objects.filter(establishment=current_establishment, is_active=True).order_by('order', 'name')
        
        # Получаем ID выбранной категории из GET параметра
        category_id = request.GET.get('category')
        
        # Текущее время в часовом поясе заведения
        establishment_tz = pytz.timezone(current_establishment.timezone)
        now = timezone.now().astimezone(establishment_tz)
        
        # Базовый queryset - только просроченные
        expired_products = ProductDelete.objects.filter(
            establishment=current_establishment,
            expiration_time__lt=now
        ).select_related('category', 'employee', 'user').order_by('-expiration_time')
        
        # Подсчет количества просроченных по категориям
        for category in categories:
            count = expired_products.filter(category=category).count()
            category_counts[category.id] = count
        
        # Подсчет просроченных без категории
        uncategorized_count = expired_products.filter(category__isnull=True).count()
        
        # Фильтрация по категории
        if category_id:
            if category_id == 'uncategorized':
                filtered_expired = expired_products.filter(category__isnull=True)
                selected_category = {'id': 'uncategorized', 'name': 'Без категории', 'color': '#6c757d'}
            elif category_id == 'all':
                filtered_expired = expired_products
                selected_category = {'id': 'all', 'name': 'Все просроченные', 'color': '#dc3545'}
            else:
                try:
                    selected_category = Category.objects.get(id=category_id, establishment=current_establishment)
                    filtered_expired = expired_products.filter(category=selected_category)
                except Category.DoesNotExist:
                    filtered_expired = expired_products
                    selected_category = {'id': 'all', 'name': 'Все просроченные', 'color': '#dc3545'}
        else:
            filtered_expired = expired_products
            selected_category = {'id': 'all', 'name': 'Все просроченные', 'color': '#dc3545'}
    
    return render(request, 'labels/expired_products.html', {
        'user_establishments': user_establishments,
        'current_establishment': current_establishment,
        'expired_products': expired_products,
        'filtered_expired': filtered_expired,
        'categories': categories,
        'selected_category': selected_category,
        'category_counts': category_counts,
        'uncategorized_count': uncategorized_count,
    })

# views.py - добавьте новые функции

@login_required
def delete_expired_product(request, product_id):
    """Удаление одного просроченного продукта"""
    product = get_object_or_404(ProductDelete, id=product_id)
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=product.establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Продукт "{product_name}" удален из просроченных')
        return redirect(f'{reverse("expired_products")}?establishment={product.establishment.id}')
    
    return render(request, 'labels/delete_expired_confirm.html', {
        'product': product
    })

@login_required
def delete_all_expired(request):
    """Удаление всех просроченных продуктов в заведении"""
    establishment_id = request.GET.get('establishment')
    if not establishment_id:
        messages.error(request, 'Не указано заведение')
        return redirect('expired_products')
    
    establishment = get_object_or_404(Establishment, id=establishment_id)
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        # Получаем часовой пояс заведения
        establishment_tz = pytz.timezone(establishment.timezone)
        now = timezone.now().astimezone(establishment_tz)
        
        # Удаляем все просроченные продукты
        deleted_count = ProductDelete.objects.filter(
            establishment=establishment,
            expiration_time__lt=now
        ).count()
        
        ProductDelete.objects.filter(
            establishment=establishment,
            expiration_time__lt=now
        ).delete()
        
        messages.success(request, f'Удалено {deleted_count} просроченных продуктов')
        return redirect(f'{reverse("expired_products")}?establishment={establishment.id}')
    
    return render(request, 'labels/delete_all_expired_confirm.html', {
        'establishment': establishment
    })

@login_required
def delete_expired_by_category(request, category_id):
    """Удаление просроченных продуктов по категории"""
    category = get_object_or_404(Category, id=category_id)
    establishment = category.establishment
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    if request.method == 'POST':
        # Получаем часовой пояс заведения
        establishment_tz = pytz.timezone(establishment.timezone)
        now = timezone.now().astimezone(establishment_tz)
        
        # Удаляем просроченные продукты в категории
        deleted_count = ProductDelete.objects.filter(
            establishment=establishment,
            category=category,
            expiration_time__lt=now
        ).count()
        
        ProductDelete.objects.filter(
            establishment=establishment,
            category=category,
            expiration_time__lt=now
        ).delete()
        
        messages.success(request, f'Удалено {deleted_count} просроченных продуктов из категории "{category.name}"')
        return redirect(f'{reverse("expired_products")}?establishment={establishment.id}')
    
    return render(request, 'labels/delete_expired_by_category_confirm.html', {
        'category': category,
        'establishment': establishment
    })



# views.py - обновленная функция

# views.py - исправленная функция reprint_expired_products

@login_required
def reprint_expired_products(request):
    """Перепечатка просроченных продуктов (печать существующих с новой датой)"""
    establishment_id = request.GET.get('establishment')
    if not establishment_id:
        messages.error(request, 'Не указано заведение')
        return redirect('expired_products')
    
    establishment = get_object_or_404(Establishment, id=establishment_id)
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return HttpResponseForbidden("У вас нет доступа к этому заведению")
    
    # Получаем часовой пояс заведения
    establishment_tz = pytz.timezone(establishment.timezone)
    now = timezone.now().astimezone(establishment_tz)
    
    # Получаем все просроченные продукты
    expired_products = ProductDelete.objects.filter(
        establishment=establishment,
        expiration_time__lt=now
    ).select_related('category', 'employee', 'user')
    
    if not expired_products.exists():
        messages.warning(request, 'Нет просроченных продуктов для перепечатки')
        return redirect(f'{reverse("expired_products")}?establishment={establishment.id}')
    
    # ПОЛУЧАЕМ ТЕКУЩЕГО СОТРУДНИКА
    try:
        current_session = EmployeeSession.objects.filter(
            user=request.user,
            establishment=establishment,
            is_active=True
        ).select_related('employee').first()
        
        if current_session:
            marking_person = current_session.employee.name
        else:
            marking_person = request.user.get_full_name() or request.user.username
    except EmployeeSession.DoesNotExist:
        marking_person = request.user.get_full_name() or request.user.username
    
    # Подготавливаем данные для печати (без создания новых маркировок)
    labels_data = []
    
    for product in expired_products:
        # Рассчитываем время для печати (текущее время)
        print_time = round_to_15_minutes(now)
        
        # Рассчитываем новое время истечения срока (от текущего времени)
        if product.duration_unit == 'hours':
            new_expiration_time = print_time + timedelta(hours=product.storage_duration)
        else:  # days
            new_expiration_time = print_time + timedelta(days=product.storage_duration)
        
        new_expiration_time = round_to_15_minutes(new_expiration_time)
        
        # Обновляем время печати и истечения в существующей записи ProductDelete
        product.printed_at = print_time
        product.expiration_time = new_expiration_time
        product.save(update_fields=['printed_at', 'expiration_time'])
        
        labels_data.append({
            'name': product.name,
            'storage_temperature': product.storage_temperature,
            'storage_duration': product.storage_duration,
            'duration_unit': product.duration_unit,
            'category': product.category,
            'print_time': print_time,
            'expiration_time': new_expiration_time,
            'get_storage_period_text': product.get_storage_period_text(),
            'marking_person': marking_person,
            'product': product,  # Сохраняем ссылку на продукт для дополнительных данных
        })
    
    messages.success(request, f'Подготовлено {len(labels_data)} просроченных продуктов к перепечатке')
    
    # Печатаем все маркировки
    html_content = render_to_string('labels/print_reprinted_labels.html', {
        'labels_data': labels_data,
        'establishment': establishment,
        'total_count': len(labels_data),
        'timezone_name': establishment_tz.zone,
        'print_time': round_to_15_minutes(now),
        'is_reprint': True,  # Флаг что это перепечатка
    })
    
    response = HttpResponse(html_content)
    return response

# views.py

from django.http import JsonResponse

@login_required
def start_employee_session_ajax(request, employee_id):
    """Начало работы от имени сотрудника (AJAX)"""
    employee = get_object_or_404(Employee, id=employee_id)
    establishment = employee.establishment
    
    # Проверяем доступ пользователя к заведению
    if not EstablishmentMember.objects.filter(
        user=request.user, 
        establishment=establishment
    ).exists():
        return JsonResponse({'success': False, 'error': 'У вас нет доступа'})
    
    # Завершаем предыдущие активные сессии
    EmployeeSession.objects.filter(
        user=request.user,
        establishment=establishment,
        is_active=True
    ).update(is_active=False, end_time=timezone.now())
    
    # Создаем новую сессию
    session = EmployeeSession.objects.create(
        user=request.user,
        establishment=establishment,
        employee=employee
    )
    
    # СОХРАНЯЕМ В СЕССИИ
    request.session['current_establishment_id'] = establishment.id
    request.session['current_employee_id'] = employee.id
    request.session['current_employee_name'] = employee.name
    
    return JsonResponse({
        'success': True,
        'message': f'Теперь вы работаете от имени: {employee.name}',
        'employee_name': employee.name,
        'employee_id': employee.id
    })

@login_required
def stop_employee_session_ajax(request):
    """Завершение текущей сессии сотрудника (AJAX)"""
    establishment_id = request.GET.get('establishment')
    
    if establishment_id:
        EmployeeSession.objects.filter(
            user=request.user,
            establishment_id=establishment_id,
            is_active=True
        ).update(is_active=False, end_time=timezone.now())
        
        # Удаляем из сессии
        if 'current_employee_id' in request.session:
            del request.session['current_employee_id']
        if 'current_employee_name' in request.session:
            del request.session['current_employee_name']
        
        return JsonResponse({
            'success': True,
            'message': 'Сессия сотрудника завершена'
        })
    
    return JsonResponse({'success': False, 'error': 'Заведение не указано'})


from .models import UserApiKey

@login_required
def api_tester(request):
    api_key = UserApiKey.get_or_create_for(request.user)
    return render(request, 'labels/api_tester.html', {
        'api_key': api_key,
    })



from django.views.decorators.http import require_POST


@login_required
def api_key_page(request):
    """Показать ключ пользователя (создать, если нет)"""
    api_key = UserApiKey.get_or_create_for(request.user)
    return render(request, 'labels/api_key.html', {'api_key': api_key})


@login_required
@require_POST
def api_key_regenerate(request):
    """Пересоздать ключ — старый перестанет работать"""
    UserApiKey.regenerate_for(request.user)
    messages.success(request, 'API-ключ обновлён. Старый ключ больше не работает.')
    return redirect('api_key_page')


@login_required
def app_connect(request):
    """Страница с API-ключом и инструкцией для подключения приложения."""
    api_key = UserApiKey.get_or_create_for(request.user)

    if request.method == 'POST' and 'regenerate' in request.POST:
        UserApiKey.regenerate_for(request.user)
        messages.success(request, 'API-ключ обновлён. Старый ключ больше не работает.')
        return redirect('app_connect')

    download_url = 'https://markirovki24.ru/media/FoodSafe.zip'
    app_version = '1.1'

    # Добавляем контекст для видео из настроек
    context = {
        'api_key': api_key,
        'download_url': download_url,
        'app_version': app_version,
        'video_url': settings.VIDEO_INSTRUCTION_URL,
        'video_poster': settings.VIDEO_INSTRUCTION_POSTER,
        'video_title': settings.VIDEO_INSTRUCTION_TITLE,
    }

    return render(request, 'labels/app_connect.html', context)


# views.py
@login_required
def print_page(request, establishment_id):
    """Страница удалённой печати — для телефонов и любых устройств."""
    establishment = get_object_or_404(
        Establishment, id=establishment_id,
        establishmentmember__user=request.user,
    )

    # --- Сотрудник: хранится в сессии Django, у каждого устройства свой ---
    if request.method == 'POST' and 'employee_id' in request.POST:
        emp_id = request.POST.get('employee_id')
        if emp_id and emp_id != 'none':
            request.session[f'print_employee_{establishment.id}'] = int(emp_id)
        else:
            request.session.pop(f'print_employee_{establishment.id}', None)
        return redirect('print_page', establishment_id=establishment.id)

    employees = Employee.objects.filter(
        establishment=establishment, is_active=True
    ).order_by('name')

    # Текущий выбранный сотрудник для этого устройства
    current_employee = None
    saved_id = request.session.get(f'print_employee_{establishment.id}')
    if saved_id:
        current_employee = employees.filter(id=saved_id).first()

    # Категории и маркировки
    categories = Category.objects.filter(
        establishment=establishment, is_active=True,
    ).order_by('order', 'name')
    labels = ProductLabel.objects.filter(
        establishment=establishment,
    ).select_related('category', 'employee').order_by('-created_at')

    # Фильтр по категории
    category_id = request.GET.get('category')
    selected_category = None
    if category_id == 'all' or not category_id:
        selected_category = {'id': 'all', 'name': 'Все маркировки'}
    elif category_id == 'uncategorized':
        labels = labels.filter(category__isnull=True)
        selected_category = {'id': 'uncategorized', 'name': 'Без категории'}
    else:
        try:
            selected_category = categories.get(id=category_id)
            labels = labels.filter(category=selected_category)
        except Category.DoesNotExist:
            selected_category = {'id': 'all', 'name': 'Все маркировки'}

    # Задания, созданные с этого устройства за последние 5 минут
    recent_jobs = PrintJob.objects.filter(
        establishment=establishment,
        user=request.user,
    ).order_by('-created_at')[:10]

    return render(request, 'labels/print_page.html', {
        'establishment': establishment,
        'employees': employees,
        'current_employee': current_employee,
        'categories': categories,
        'labels': labels,
        'selected_category': selected_category,
        'recent_jobs': recent_jobs,
    })


@login_required
@require_POST
def print_create_job(request, label_id):
    label = get_object_or_404(ProductLabel, id=label_id)
    if not EstablishmentMember.objects.filter(
        user=request.user, establishment=label.establishment,
    ).exists():
        return JsonResponse({'success': False, 'error': 'Нет доступа'}, status=403)

    employee = None
    saved_id = request.session.get(f'print_employee_{label.establishment.id}')
    if saved_id:
        employee = Employee.objects.filter(
            id=saved_id, establishment=label.establishment, is_active=True,
        ).first()

    est_tz = pytz.timezone(label.establishment.timezone)
    manual_time = request.POST.get('manual_time')

    if manual_time:
        try:
            print_time = _parse_manual_time(manual_time, est_tz)
        except (ValueError, TypeError):
            return JsonResponse(
                {'success': False, 'error': 'Неверный формат времени'},
                status=400,
            )
    else:
        now = timezone.now().astimezone(est_tz)
        minutes = math.floor(now.minute / 15) * 15
        print_time = now.replace(minute=minutes, second=0, microsecond=0)

    # Срок годности
    duration = label.storage_duration or 0
    if label.duration_unit == 'hours':
        expiration = print_time + timedelta(hours=duration)
    else:
        expiration = print_time + timedelta(days=duration)

    minutes = math.floor(expiration.minute / 15) * 15
    expiration = expiration.replace(minute=minutes, second=0, microsecond=0)

    marked_by = employee.name if employee else (
        request.user.get_full_name() or request.user.username
    )

    job = PrintJob.objects.create(
        establishment=label.establishment,
        user=request.user,
        employee=employee,
        label=label,
        payload={
            'label_id': label.id,
            'name': label.name,
            'storage_temperature': label.storage_temperature,
            'storage_duration': label.storage_duration,
            'duration_unit': label.duration_unit,
            'storage_period_text': label.get_storage_period_text(),
            'marked_by': marked_by,
            'print_time_str': print_time.strftime('%d.%m.%Y %H:%M'),
            'expiration_time_str': expiration.strftime('%d.%m.%Y %H:%M'),
            'print_time_iso': print_time.isoformat(),
            'expiration_time_iso': expiration.isoformat(),
        },
    )

    return JsonResponse({
        'success': True,
        'job_id': job.id,
        'marked_by': marked_by,
        'print_time_str': job.payload['print_time_str'],
        'expiration_time_str': job.payload['expiration_time_str'],
    })



@login_required
@require_POST
def print_create_cart(request, establishment_id):
    """Создаёт сразу N заданий из корзины (переданной в POST как JSON)."""
    establishment = get_object_or_404(
        Establishment, id=establishment_id,
        establishmentmember__user=request.user,
    )

    import json
    try:
        cart = json.loads(request.POST.get('cart', '{}'))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Неверный формат корзины'}, status=400)

    if not cart:
        return JsonResponse({'success': False, 'error': 'Корзина пуста'}, status=400)

    # Сотрудник из сессии
    employee = None
    saved_id = request.session.get(f'print_employee_{establishment.id}')
    if saved_id:
        employee = Employee.objects.filter(
            id=saved_id, establishment=establishment, is_active=True,
        ).first()

    # Ручное время
    est_tz = pytz.timezone(establishment.timezone)
    manual_time = request.POST.get('manual_time')

    if manual_time:
        try:
            print_time = _parse_manual_time(manual_time, est_tz)
        except (ValueError, TypeError):
            return JsonResponse(
                {'success': False, 'error': 'Неверный формат времени'},
                status=400,
            )
    else:
        now = timezone.now().astimezone(est_tz)
        minutes = math.floor(now.minute / 15) * 15
        print_time = now.replace(minute=minutes, second=0, microsecond=0)

    marked_by = employee.name if employee else (
        request.user.get_full_name() or request.user.username
    )

    created = 0
    for label_id, quantity in cart.items():
        try:
            label = ProductLabel.objects.get(id=int(label_id), establishment=establishment)
        except (ProductLabel.DoesNotExist, ValueError):
            continue

        duration = label.storage_duration or 0
        if label.duration_unit == 'hours':
            expiration = print_time + timedelta(hours=duration)
        else:
            expiration = print_time + timedelta(days=duration)
        minutes = math.floor(expiration.minute / 15) * 15
        expiration = expiration.replace(minute=minutes, second=0, microsecond=0)

        for _ in range(int(quantity)):
            PrintJob.objects.create(
                establishment=establishment,
                user=request.user,
                employee=employee,
                label=label,
                payload={
                    'label_id': label.id,
                    'name': label.name,
                    'storage_temperature': label.storage_temperature,
                    'storage_duration': label.storage_duration,
                    'duration_unit': label.duration_unit,
                    'storage_period_text': label.get_storage_period_text(),
                    'marked_by': marked_by,
                    'print_time_str': print_time.strftime('%d.%m.%Y %H:%M'),
                    'expiration_time_str': expiration.strftime('%d.%m.%Y %H:%M'),
                    'print_time_iso': print_time.isoformat(),
                    'expiration_time_iso': expiration.isoformat(),
                },
            )
            created += 1

    return JsonResponse({'success': True, 'created': created})


def _parse_manual_time(manual_time, est_tz):
    """
    Безопасно парсит строку из <input type="datetime-local"> и
    возвращает timezone-aware datetime в часовом поясе заведения.
    Бросает ValueError, если строка невалидная.
    """
    s = (manual_time or '').strip()
    if not s:
        raise ValueError('empty')

    # Если пришло с Z или миллисекундами — обрезаем
    s = s.replace('Z', '+00:00')
    if '.' in s:
        # 2026-10-06T14:30:00.123 → 2026-10-06T14:30:00
        s = s.split('.')[0]

    # Если есть таймзона (+07:00), отрезаем — время локальное для заведения
    if len(s) >= 6 and s[-6] in ('+', '-') and ':' in s[-6:]:
        s = s[:-6]

    dt_naive = datetime.fromisoformat(s)

    # Приводим к aware в часовом поясе заведения
    if dt_naive.tzinfo is None:
        return est_tz.localize(dt_naive)
    else:
        return dt_naive.astimezone(est_tz)


# views.py

@login_required
@require_GET
def print_job_status(request, job_id):
    """Статус PrintJob для индикатора печати на фронте."""
    job = get_object_or_404(PrintJob, id=job_id)

    # Проверяем доступ: пользователь должен быть участником заведения
    if not EstablishmentMember.objects.filter(
        user=request.user,
        establishment=job.establishment,
    ).exists():
        return JsonResponse({'success': False, 'error': 'Нет доступа'}, status=403)

    return JsonResponse({
        'success': True,
        'job_id': job.id,
        'status': job.status,          # pending / printing / done / error
        'printed_at': job.printed_at.isoformat() if job.printed_at else None,
        'error_message': job.error_message or '',
    })