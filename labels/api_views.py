# labels/api_views.py
import pytz
from django.http import JsonResponse
from django.utils import timezone
from .models import (
    UserApiKey, Establishment, EstablishmentMember,
    Category, ProductLabel, Employee, LabelCart, CartItem,
)
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction, IntegrityError
from datetime import timedelta

# ---------- Вспомогательное ----------

def _auth_user(request):
    auth = request.headers.get('Authorization', '').strip()

    if not auth:
        # Fallback для хостингов, где Authorization не доходит
        auth = request.POST.get('key', '').strip() or request.GET.get('key', '').strip()

    if not auth:
        return None

    for prefix in ('Bearer ', 'Token '):
        if auth.startswith(prefix):
            auth = auth[len(prefix):].strip()
            break

    try:
        api_key = UserApiKey.objects.select_related('user').get(key=auth)
    except UserApiKey.DoesNotExist:
        return None

    now = timezone.now()
    if not api_key.last_used_at or (now - api_key.last_used_at).total_seconds() > 60:
        api_key.last_used_at = now
        api_key.save(update_fields=['last_used_at'])

    return api_key.user


def _json_error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)


def _check_access(user, establishment_id):
    """Возвращает (establishment, membership) или (None, None)"""
    try:
        est = Establishment.objects.get(id=establishment_id)
    except Establishment.DoesNotExist:
        return None, None
    try:
        m = EstablishmentMember.objects.get(user=user, establishment=est)
    except EstablishmentMember.DoesNotExist:
        return None, None
    return est, m


# ---------- /api/me/ ----------

@require_GET
def api_me(request):
    """Проверка ключа + список заведений пользователя."""
    user = _auth_user(request)
    if user is None:
        return _json_error('Неверный или отозванный ключ', 401)

    memberships = EstablishmentMember.objects.filter(user=user).select_related('establishment')
    return JsonResponse({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.get_full_name(),
        },
        'establishments': [{
            'id': m.establishment.id,
            'name': m.establishment.name,
            'role': m.role,
            'timezone': m.establishment.timezone,
            'invite_code': m.establishment.invite_code,
            'paid_until': m.establishment.paid_until.isoformat()
                          if m.establishment.paid_until else None,
            'is_paid': m.establishment.is_paid(),
            'days_left': m.establishment.days_left(),
        } for m in memberships],
    })


# ---------- /api/establishments/<id>/labels/ ----------

@require_GET
def api_labels(request, establishment_id):
    """Список маркировок заведения.
    GET ?category=<id>|uncategorized|all
    """
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)

    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    qs = ProductLabel.objects.filter(establishment=est).select_related(
        'category', 'employee', 'user'
    ).order_by('-created_at')

    cat = request.GET.get('category')
    if cat == 'uncategorized':
        qs = qs.filter(category__isnull=True)
    elif cat and cat != 'all':
        try:
            qs = qs.filter(category_id=int(cat))
        except (ValueError, TypeError):
            pass

    return JsonResponse({
        'success': True,
        'establishment': {'id': est.id, 'name': est.name, 'timezone': est.timezone},
        'labels': [{
            'id': l.id,
            'name': l.name,
            'category': {
                'id': l.category.id,
                'name': l.category.name,
                'color': l.category.color,
            } if l.category else None,
            'storage_temperature': l.storage_temperature,
            'storage_duration': l.storage_duration,
            'duration_unit': l.duration_unit,
            'storage_period_text': l.get_storage_period_text(),
            'marked_by': l.get_marking_person(),
            'employee': {
                'id': l.employee.id,
                'name': l.employee.name,
            } if l.employee else None,
            'created_at': l.created_at.isoformat(),
            'last_printed_at': l.last_printed_at.isoformat() if l.last_printed_at else None,
            'manual_print_time': l.manual_print_time.isoformat() if l.manual_print_time else None,
        } for l in qs],
    })


# ---------- /api/establishments/<id>/categories/ ----------

@require_GET
def api_categories(request, establishment_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)

    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    categories = Category.objects.filter(establishment=est).order_by('order', 'name')
    return JsonResponse({
        'success': True,
        'categories': [{
            'id': c.id,
            'name': c.name,
            'color': c.color,
            'order': c.order,
            'is_active': c.is_active,
        } for c in categories],
    })


# ---------- /api/establishments/<id>/employees/ ----------

@require_GET
def api_employees(request, establishment_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)

    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    employees = Employee.objects.filter(establishment=est).order_by('name')
    return JsonResponse({
        'success': True,
        'employees': [{
            'id': e.id,
            'name': e.name,
            'position': e.position,
            'is_active': e.is_active,
        } for e in employees],
    })


# ---------- /api/establishments/<id>/cart/ ----------

@require_GET
def api_cart(request, establishment_id):
    """Содержимое корзины пользователя в этом заведении."""
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)

    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    try:
        cart = LabelCart.objects.get(user=user, establishment=est)
    except LabelCart.DoesNotExist:
        return JsonResponse({
            'success': True,
            'items': [],
            'total_count': 0,
            'unique_count': 0,
        })

    items = cart.cart_items.select_related(
        'label', 'label__category', 'label__employee'
    ).all()

    return JsonResponse({
        'success': True,
        'total_count': cart.get_total_items_count(),
        'unique_count': cart.get_total_labels(),
        'items': [{
            'id': item.id,
            'label_id': item.label.id,
            'name': item.label.name,
            'category': {
                'id': item.label.category.id,
                'name': item.label.category.name,
                'color': item.label.category.color,
            } if item.label.category else None,
            'storage_temperature': item.label.storage_temperature,
            'storage_duration': item.label.storage_duration,
            'duration_unit': item.label.duration_unit,
            'storage_period_text': item.label.get_storage_period_text(),
            'marked_by': item.label.get_marking_person(),
            'quantity': item.quantity,
            'added_at': item.added_at.isoformat(),
        } for item in items],
    })


@csrf_exempt
@require_POST
def api_label_create(request, establishment_id):
    """
    Создаёт новую маркировку.
    POST-параметры:
        name (str, обязательно)
        storage_temperature (str, опц., по умолчанию "+4°C до +6°C")
        storage_duration (int > 0, обязательно)
        duration_unit (hours|days, обязательно)
        category_id (int, опц.)
        employee_id (int, опц.) — если не указан, берётся текущая
                                 сессия сотрудника пользователя
    """
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)

    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    name = (request.POST.get('name') or '').strip()
    if not name:
        return _json_error('Поле name обязательно', 400)
    if len(name) > 200:
        return _json_error('Название не должно превышать 200 символов', 400)

    try:
        storage_duration = int(request.POST.get('storage_duration', 0))
    except (ValueError, TypeError):
        return _json_error('storage_duration должен быть числом', 400)
    if storage_duration <= 0:
        return _json_error('storage_duration должен быть > 0', 400)
    if storage_duration > 10000:
        return _json_error('storage_duration слишком большой', 400)

    duration_unit = request.POST.get('duration_unit', 'hours')
    if duration_unit not in ('hours', 'days'):
        return _json_error('duration_unit: hours или days', 400)

    storage_temperature = (request.POST.get('storage_temperature')
                           or '+4°C до +6°C').strip()
    if len(storage_temperature) > 50:
        return _json_error('storage_temperature слишком длинное', 400)

    # Категория
    category = None
    category_id = request.POST.get('category_id')
    if category_id:
        try:
            category = Category.objects.get(id=category_id, establishment=est)
        except Category.DoesNotExist:
            return _json_error('Категория не найдена', 400)

    # Сотрудник
    employee = None
    employee_id = request.POST.get('employee_id')
    if employee_id:
        try:
            employee = Employee.objects.get(id=employee_id, establishment=est)
        except Employee.DoesNotExist:
            return _json_error('Сотрудник не найден', 400)
    else:
        # Пробуем активную сессию сотрудника
        from .models import EmployeeSession
        session = EmployeeSession.objects.filter(
            user=user, establishment=est, is_active=True
        ).select_related('employee').first()
        if session:
            employee = session.employee

    with transaction.atomic():
        label = ProductLabel.objects.create(
            establishment=est,
            user=user,
            employee=employee,
            category=category,
            name=name,
            storage_temperature=storage_temperature,
            storage_duration=storage_duration,
            duration_unit=duration_unit,
        )

    return JsonResponse({
        'success': True,
        'label': {
            'id': label.id,
            'name': label.name,
            'category': {
                'id': category.id,
                'name': category.name,
                'color': category.color,
            } if category else None,
            'storage_temperature': label.storage_temperature,
            'storage_duration': label.storage_duration,
            'duration_unit': label.duration_unit,
            'storage_period_text': label.get_storage_period_text(),
            'marked_by': label.get_marking_person(),
            'employee': {
                'id': employee.id,
                'name': employee.name,
            } if employee else None,
            'created_at': label.created_at.isoformat(),
            'last_printed_at': None,
            'manual_print_time': None,
        }
    })


# ============================================================
# СОТРУДНИКИ
# ============================================================

@csrf_exempt
@require_POST
def api_employee_create(request, establishment_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    name = (request.POST.get('name') or '').strip()
    position = (request.POST.get('position') or '').strip()
    if not name:
        return _json_error('Поле name обязательно', 400)
    if len(name) > 100:
        return _json_error('Имя слишком длинное', 400)

    if Employee.objects.filter(establishment=est, name=name).exists():
        return _json_error('Сотрудник с таким именем уже есть', 400)

    try:
        emp = Employee.objects.create(
            establishment=est,
            name=name,
            position=position,
        )
    except IntegrityError:
        return _json_error('Сотрудник с таким именем уже есть', 400)

    return JsonResponse({
        'success': True,
        'employee': {
            'id': emp.id,
            'name': emp.name,
            'position': emp.position,
            'is_active': emp.is_active,
        }
    })


@csrf_exempt
@require_POST
def api_employee_update(request, establishment_id, employee_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    try:
        emp = Employee.objects.get(id=employee_id, establishment=est)
    except Employee.DoesNotExist:
        return _json_error('Сотрудник не найден', 404)

    name = (request.POST.get('name') or '').strip()
    position = (request.POST.get('position') or '').strip()
    if not name:
        return _json_error('Поле name обязательно', 400)

    # Проверка уникальности (кроме самого себя)
    if Employee.objects.filter(establishment=est, name=name).exclude(id=emp.id).exists():
        return _json_error('Сотрудник с таким именем уже есть', 400)

    emp.name = name
    emp.position = position
    emp.save()

    return JsonResponse({
        'success': True,
        'employee': {
            'id': emp.id,
            'name': emp.name,
            'position': emp.position,
            'is_active': emp.is_active,
        }
    })


@csrf_exempt
@require_POST
def api_employee_delete(request, establishment_id, employee_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    try:
        emp = Employee.objects.get(id=employee_id, establishment=est)
    except Employee.DoesNotExist:
        return _json_error('Сотрудник не найден', 404)

    emp.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def api_employee_toggle(request, establishment_id, employee_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    try:
        emp = Employee.objects.get(id=employee_id, establishment=est)
    except Employee.DoesNotExist:
        return _json_error('Сотрудник не найден', 404)

    emp.is_active = not emp.is_active
    emp.save(update_fields=['is_active'])
    return JsonResponse({
        'success': True,
        'employee': {
            'id': emp.id,
            'name': emp.name,
            'position': emp.position,
            'is_active': emp.is_active,
        }
    })


# ============================================================
# КАТЕГОРИИ
# ============================================================

@csrf_exempt
@require_POST
def api_category_create(request, establishment_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    name = (request.POST.get('name') or '').strip()
    color = (request.POST.get('color') or '#6c757d').strip()
    order = request.POST.get('order', '0')

    if not name:
        return _json_error('Поле name обязательно', 400)
    if len(name) > 100:
        return _json_error('Название слишком длинное', 400)

    try:
        order = int(order)
    except (ValueError, TypeError):
        order = 0

    if Category.objects.filter(establishment=est, name=name).exists():
        return _json_error('Категория с таким именем уже есть', 400)

    cat = Category.objects.create(
        establishment=est,
        name=name,
        color=color,
        order=order,
        is_active=True,
    )
    return JsonResponse({
        'success': True,
        'category': {
            'id': cat.id,
            'name': cat.name,
            'color': cat.color,
            'order': cat.order,
            'is_active': cat.is_active,
        }
    })


@csrf_exempt
@require_POST
def api_category_update(request, establishment_id, category_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    try:
        cat = Category.objects.get(id=category_id, establishment=est)
    except Category.DoesNotExist:
        return _json_error('Категория не найдена', 404)

    name = (request.POST.get('name') or '').strip()
    color = (request.POST.get('color') or cat.color).strip()
    order = request.POST.get('order', str(cat.order))

    if not name:
        return _json_error('Поле name обязательно', 400)

    if Category.objects.filter(establishment=est, name=name).exclude(id=cat.id).exists():
        return _json_error('Категория с таким именем уже есть', 400)

    try:
        order = int(order)
    except (ValueError, TypeError):
        order = cat.order

    cat.name = name
    cat.color = color
    cat.order = order
    cat.save()

    return JsonResponse({
        'success': True,
        'category': {
            'id': cat.id,
            'name': cat.name,
            'color': cat.color,
            'order': cat.order,
            'is_active': cat.is_active,
        }
    })


@csrf_exempt
@require_POST
def api_category_delete(request, establishment_id, category_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    try:
        cat = Category.objects.get(id=category_id, establishment=est)
    except Category.DoesNotExist:
        return _json_error('Категория не найдена', 404)

    with transaction.atomic():
        # Убираем категорию у маркировок
        ProductLabel.objects.filter(category=cat).update(category=None)
        cat.delete()

    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def api_category_toggle(request, establishment_id, category_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    try:
        cat = Category.objects.get(id=category_id, establishment=est)
    except Category.DoesNotExist:
        return _json_error('Категория не найдена', 404)

    cat.is_active = not cat.is_active
    cat.save(update_fields=['is_active'])
    return JsonResponse({
        'success': True,
        'category': {
            'id': cat.id,
            'name': cat.name,
            'color': cat.color,
            'order': cat.order,
            'is_active': cat.is_active,
        }
    })


# api_views.py
from .models import PrintJob


@require_GET
def api_print_pending(request, establishment_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)
    est, _ = _check_access(user, establishment_id)
    if est is None:
        return _json_error('Нет доступа к заведению', 403)

    # Отменяем задания, которые висят больше 10 минут
    stale_before = timezone.now() - timedelta(minutes=10)
    PrintJob.objects.filter(
        establishment=est,
        status='pending',
        created_at__lt=stale_before,
    ).update(status='error', error_message='Планшет не отвечал более 10 минут')

    jobs = PrintJob.objects.filter(
        establishment=est, status='pending'
    ).order_by('created_at')[:20]

    result = []
    for job in jobs:
        result.append({'id': job.id, 'payload': job.payload})
        job.status = 'printing'
        job.save(update_fields=['status'])

    return JsonResponse({'success': True, 'jobs': result})


@csrf_exempt
@require_POST
def api_print_complete(request, job_id):
    user = _auth_user(request)
    if user is None:
        return _json_error('Unauthorized', 401)

    try:
        job = PrintJob.objects.get(id=job_id)
    except PrintJob.DoesNotExist:
        return _json_error('Задание не найдено', 404)

    est, _ = _check_access(user, job.establishment.id)
    if est is None:
        return _json_error('Нет доступа', 403)

    status = request.POST.get('status', 'done')
    job.status = status
    job.printed_at = timezone.now()

    if status == 'done':
        p = job.payload
        # Восстанавливаем точное время из payload
        from datetime import datetime
        try:
            print_dt = datetime.fromisoformat(p.get('print_time_iso', ''))
            exp_dt = datetime.fromisoformat(p.get('expiration_time_iso', ''))
        except (ValueError, TypeError):
            print_dt = exp_dt = timezone.now()

        # ProductDelete.objects.create(
        #     establishment=job.establishment,
        #     user=job.user,
        #     employee=job.employee,
        #     category=job.label.category if job.label else None,
        #     name=p.get('name', ''),
        #     storage_temperature=p.get('storage_temperature', ''),
        #     storage_duration=p.get('storage_duration', 0),
        #     duration_unit=p.get('duration_unit', 'hours'),
        #     created_at=timezone.now(),
        #     printed_at=print_dt,
        #     expiration_time=exp_dt,
        #     original_label=job.label,
        # )
    else:
        job.error_message = (request.POST.get('error') or '')[:1000]

    job.save()
    return JsonResponse({'success': True})