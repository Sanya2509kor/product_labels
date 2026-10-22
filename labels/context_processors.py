from .models import EmployeeSession, LabelCart

def current_employee(request):
    """Добавляет информацию о текущем сотруднике в контекст"""
    if request.user.is_authenticated:
        # Получаем текущее заведение из GET параметра или сессии
        establishment_id = request.GET.get('establishment') or request.session.get('current_establishment_id')
        
        if establishment_id:
            try:
                active_session = EmployeeSession.objects.filter(
                    user=request.user,
                    establishment_id=establishment_id,
                    is_active=True
                ).select_related('employee').first()
                
                if active_session:
                    return {
                        'current_employee': active_session.employee,
                        'current_employee_session': active_session
                    }
            except:
                pass
    
    return {
        'current_employee': None,
        'current_employee_session': None
    }


def cart_count(request):
    if request.user.is_authenticated:
        establishment_id = request.GET.get('establishment') or request.session.get('current_establishment_id')
        if establishment_id:
            try:
                cart = LabelCart.objects.get(
                    user=request.user,
                    establishment_id=establishment_id
                )
                return {'cart_count': cart.get_total_labels()}
            except LabelCart.DoesNotExist:
                pass
    return {'cart_count': 0}



# labels/context_processors.py

from .models import ProductDelete
from django.utils import timezone
import pytz

def expired_products_count(request):
    """Контекстный процессор для подсчета просроченных продуктов"""
    context = {
        'expired_products_count': 0,
        'has_expired_products': False
    }
    
    if request.user.is_authenticated:
        # Получаем все заведения пользователя через членство
        user_establishments = request.user.establishmentmember_set.all().values_list('establishment', flat=True)
        
        total_expired = 0
        for est_id in user_establishments:
            from .models import Establishment
            try:
                establishment = Establishment.objects.get(id=est_id)
                establishment_tz = pytz.timezone(establishment.timezone)
                now = timezone.now().astimezone(establishment_tz)
                
                expired_count = ProductDelete.objects.filter(
                    establishment=establishment,
                    expiration_time__lt=now
                ).count()
                
                total_expired += expired_count
            except:
                pass
        
        context['expired_products_count'] = total_expired
        context['has_expired_products'] = total_expired > 0
    
    return context