from django.contrib import admin
from django.contrib import messages
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django import forms
from .models import Category, ProductLabel, Establishment, EstablishmentMember, Employee, ProductDelete


@admin.register(Establishment)
class EstablishmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'invite_code', 'created_at',
                    'paid_until', 'is_paid_display']
    list_filter = ['created_at', 'paid_until']
    search_fields = ['name', 'owner__username']
    readonly_fields = ['invite_code']
    date_hierarchy = 'created_at'
    list_editable = ['paid_until']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('copy-data/', 
                 self.admin_site.admin_view(copy_establishment_data_view), 
                 name='labels_establishment_copy_data'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_copy_button'] = True
        return super().changelist_view(request, extra_context)
    
    def is_paid_display(self, obj):
        if obj.is_paid():
            days = obj.days_left()
            if days is None:
                return '∞ (не блокируется)'
            return f'✅ Активно ({days} дн.)'
        return '❌ Заблокировано'
    is_paid_display.short_description = 'Статус'

    

@admin.register(EstablishmentMember)
class EstablishmentMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'establishment', 'role', 'joined_at']
    list_filter = ['role', 'joined_at', 'establishment']
    search_fields = ['user__username', 'establishment__name']
    date_hierarchy = 'joined_at'

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'establishment', 'position', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'establishment']
    search_fields = ['name', 'position', 'establishment__name']
    date_hierarchy = 'created_at'

@admin.register(ProductLabel)
class ProductLabelAdmin(admin.ModelAdmin):
    list_display = ['name', 'establishment', 'get_marking_person', 'storage_temperature', 'get_storage_period', 'created_at', 'last_printed_at', 'category']
    list_editable = ['storage_temperature', 'category']
    list_filter = ['created_at', 'establishment', 'duration_unit']
    search_fields = ['name', 'establishment__name', 'user__username', 'employee__name']
    date_hierarchy = 'created_at'
    readonly_fields = ['last_printed_at']
    ordering = ['-last_printed_at']
    
    def get_storage_period(self, obj):
        return obj.get_storage_period_text()
    get_storage_period.short_description = 'Срок хранения'
    
    def get_marking_person(self, obj):
        return obj.get_marking_person()
    get_marking_person.short_description = 'Маркировал'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'establishment', 'color', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'establishment']
    search_fields = ['name', 'establishment__name']
    list_editable = ['order', 'is_active']
    date_hierarchy = 'created_at'


@admin.register(ProductDelete)
class ProductDeleteAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'establishment', 
        'get_category_name',
        'storage_temperature', 
        'get_storage_period', 
        'printed_at',
        'expiration_time',
        'get_days_expired',
        'get_marking_person',
        'original_label'
    ]
    list_filter = [
        'establishment', 
        'duration_unit',
        'category',
        'printed_at',
        'expiration_time'
    ]
    search_fields = [
        'name', 
        'establishment__name', 
        'user__username', 
        'employee__name'
    ]
    date_hierarchy = 'printed_at'
    readonly_fields = ['deleted_at']
    
    def get_storage_period(self, obj):
        return obj.get_storage_period_text()
    get_storage_period.short_description = 'Срок хранения'
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else 'Без категории'
    get_category_name.short_description = 'Категория'
    
    def get_marking_person(self, obj):
        if obj.employee:
            return obj.employee.name
        return obj.user.get_full_name() or obj.user.username if obj.user else 'Неизвестно'
    get_marking_person.short_description = 'Маркировал'
    
    def get_days_expired(self, obj):
        from django.utils import timezone
        import pytz
        
        if obj.expiration_time:
            # Получаем часовой пояс заведения
            establishment_tz = pytz.timezone(obj.establishment.timezone)
            now = timezone.now().astimezone(establishment_tz)
            
            if obj.expiration_time < now:
                delta = now - obj.expiration_time
                days = delta.days
                hours = delta.seconds // 3600
                
                if days > 0:
                    return f'{days} дн. {hours} ч.'
                else:
                    return f'{hours} ч.'
        return 'Не просрочен'
    get_days_expired.short_description = 'Просрочено'
    
    # Добавляем действия для массовых операций
    actions = ['delete_selected']



# admin.py
from django.contrib import admin
from .models import UserApiKey


@admin.register(UserApiKey)
class UserApiKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at', 'last_used_at')
    search_fields = ('user__username', 'user__email', 'key')
    readonly_fields = ('key', 'created_at', 'last_used_at')
    list_select_related = ('user',)
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False





# ========== ФОРМА ДЛЯ КОПИРОВАНИЯ ==========
class CopyLabelsForm(forms.Form):
    """Форма для выбора заведения-источника и целевого заведения"""
    source_establishment = forms.ModelChoiceField(
        queryset=Establishment.objects.all(),
        label='Откуда копировать',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    target_establishment = forms.ModelChoiceField(
        queryset=Establishment.objects.all(),
        label='Куда копировать',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    copy_categories = forms.BooleanField(
        required=False,
        initial=True,
        label='Копировать категории',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    copy_labels = forms.BooleanField(
        required=False,
        initial=True,
        label='Копировать маркировки',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    copy_employees = forms.BooleanField(
        required=False,
        initial=False,
        label='Копировать сотрудников',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    clear_target = forms.BooleanField(
        required=False,
        initial=False,
        label='Очистить целевое заведение перед копированием',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Внимание! Это удалит все существующие маркировки, категории и сотрудников в целевом заведении!'
    )


# ========== КАСТОМНЫЙ VIEW ДЛЯ КОПИРОВАНИЯ ==========
def copy_establishment_data_view(request):
    """View для копирования данных между заведениями"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет прав для этого действия')
        return HttpResponseRedirect(reverse('admin:labels_establishment_changelist'))
    
    if request.method == 'POST':
        form = CopyLabelsForm(request.POST)
        if form.is_valid():
            source = form.cleaned_data['source_establishment']
            target = form.cleaned_data['target_establishment']
            copy_categories_flag = form.cleaned_data['copy_categories']
            copy_labels_flag = form.cleaned_data['copy_labels']
            copy_employees_flag = form.cleaned_data['copy_employees']
            clear_target_flag = form.cleaned_data['clear_target']
            
            if source.id == target.id:
                messages.error(request, 'Нельзя копировать данные в то же самое заведение!')
                return HttpResponseRedirect(request.path)
            
            stats = {
                'categories_copied': 0,
                'labels_copied': 0,
                'employees_copied': 0,
                'categories_deleted': 0,
                'labels_deleted': 0,
                'employees_deleted': 0,
            }
            
            # Очистка целевого заведения
            if clear_target_flag:
                stats['labels_deleted'] = ProductLabel.objects.filter(establishment=target).count()
                ProductLabel.objects.filter(establishment=target).delete()
                
                stats['categories_deleted'] = Category.objects.filter(establishment=target).count()
                Category.objects.filter(establishment=target).delete()
                
                stats['employees_deleted'] = Employee.objects.filter(establishment=target).count()
                Employee.objects.filter(establishment=target).delete()
            
            # Словарь для сопоставления старых и новых категорий
            category_mapping = {}
            
            # Копирование категорий
            if copy_categories_flag:
                source_categories = Category.objects.filter(establishment=source)
                for src_category in source_categories:
                    # Проверяем, есть ли уже такая категория в целевом заведении
                    existing = Category.objects.filter(
                        establishment=target,
                        name=src_category.name
                    ).first()
                    
                    if existing:
                        category_mapping[src_category.id] = existing.id
                    else:
                        new_category = Category.objects.create(
                            establishment=target,
                            name=src_category.name,
                            color=src_category.color,
                            order=src_category.order,
                            is_active=src_category.is_active,
                        )
                        category_mapping[src_category.id] = new_category.id
                        stats['categories_copied'] += 1
            
            # Копирование сотрудников
            employee_mapping = {}
            if copy_employees_flag:
                source_employees = Employee.objects.filter(establishment=source)
                for src_employee in source_employees:
                    # Проверяем, есть ли уже такой сотрудник в целевом заведении
                    existing = Employee.objects.filter(
                        establishment=target,
                        name=src_employee.name
                    ).first()
                    
                    if existing:
                        employee_mapping[src_employee.id] = existing.id
                    else:
                        new_employee = Employee.objects.create(
                            establishment=target,
                            name=src_employee.name,
                            position=src_employee.position,
                            is_active=src_employee.is_active,
                        )
                        employee_mapping[src_employee.id] = new_employee.id
                        stats['employees_copied'] += 1
            
            # Копирование маркировок
            if copy_labels_flag:
                source_labels = ProductLabel.objects.filter(establishment=source)
                for src_label in source_labels:
                    # Определяем категорию для новой маркировки
                    new_category = None
                    if src_label.category_id and src_label.category_id in category_mapping:
                        try:
                            new_category = Category.objects.get(id=category_mapping[src_label.category_id])
                        except Category.DoesNotExist:
                            pass
                    
                    # Определяем сотрудника для новой маркировки
                    new_employee = None
                    if src_label.employee_id and src_label.employee_id in employee_mapping:
                        try:
                            new_employee = Employee.objects.get(id=employee_mapping[src_label.employee_id])
                        except Employee.DoesNotExist:
                            pass
                    
                    # Проверяем, есть ли уже такая маркировка в целевом заведении
                    existing = ProductLabel.objects.filter(
                        establishment=target,
                        name=src_label.name,
                        storage_temperature=src_label.storage_temperature,
                        storage_duration=src_label.storage_duration,
                        duration_unit=src_label.duration_unit,
                    ).first()
                    
                    if not existing:
                        ProductLabel.objects.create(
                            establishment=target,
                            user=request.user,  # или src_label.user
                            employee=new_employee,
                            category=new_category,
                            name=src_label.name,
                            storage_temperature=src_label.storage_temperature,
                            storage_duration=src_label.storage_duration,
                            duration_unit=src_label.duration_unit,
                            manual_print_time=None,  # Не копируем ручное время
                            last_printed_at=None,  # Не копируем историю печати
                        )
                        stats['labels_copied'] += 1
            
            # Формируем сообщение об успехе
            msg_parts = []
            if stats['categories_copied'] > 0:
                msg_parts.append(f"категорий: {stats['categories_copied']}")
            if stats['labels_copied'] > 0:
                msg_parts.append(f"маркировок: {stats['labels_copied']}")
            if stats['employees_copied'] > 0:
                msg_parts.append(f"сотрудников: {stats['employees_copied']}")
            
            if clear_target_flag:
                deleted_parts = []
                if stats['categories_deleted'] > 0:
                    deleted_parts.append(f"категорий: {stats['categories_deleted']}")
                if stats['labels_deleted'] > 0:
                    deleted_parts.append(f"маркировок: {stats['labels_deleted']}")
                if stats['employees_deleted'] > 0:
                    deleted_parts.append(f"сотрудников: {stats['employees_deleted']}")
                if deleted_parts:
                    messages.warning(request, f"Удалено из целевого заведения: {', '.join(deleted_parts)}")
            
            if msg_parts:
                messages.success(request, f"Успешно скопировано: {', '.join(msg_parts)}")
            else:
                messages.info(request, 'Нечего было копировать')
            
            return HttpResponseRedirect(reverse('admin:labels_establishment_changelist'))
    else:
        form = CopyLabelsForm()
    
    context = {
        'form': form,
        'title': 'Копирование данных между заведениями',
        'opts': Establishment._meta,
        'has_view_permission': True,
    }
    return render(request, 'admin/copy_establishment_data.html', context)