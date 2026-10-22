from django import forms
from .models import Category, ProductLabel, Establishment, Employee
from django.utils import timezone
import pytz

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'color', 'order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Овощи, Рыба, Мясо',
                'maxlength': '15'  # Добавляем ограничение для категорий
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color',
                'style': 'width: 80px; height: 38px;'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }
        labels = {
            'name': 'Название категории',
            'color': 'Цвет',
            'order': 'Порядок сортировки',
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and len(name) > 15:
            raise forms.ValidationError('Название категории не может превышать 15 символов')
        return name

# Обновим форму ProductLabelForm - добавим поле категории и ограничение
class ProductLabelForm(forms.ModelForm):
    use_manual_time = forms.BooleanField(
        required=False,
        initial=False,
        label='Установить время вручную',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Если отмечено, можно задать конкретное время маркировки'
    )
    
    manual_print_time = forms.DateTimeField(
        required=False,
        label='Время маркировки',
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
            'placeholder': 'Выберите дату и время'
        }),
        help_text='Округлится до 15 минут автоматически'
    )

    class Meta:
        model = ProductLabel
        fields = ['name', 'category', 'storage_temperature', 'storage_duration', 'duration_unit', 'use_manual_time', 'manual_print_time']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Например: Салат, Помидор, Курица',
                'maxlength': '20'  # Добавляем ограничение в 15 символов
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'storage_temperature': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: +2°C до +4°C'
            }),
            'storage_duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '24',
                'min': 1
            }),
            'duration_unit': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Название продукта',
            'category': 'Категория',
            'storage_temperature': 'Температура хранения',
            'storage_duration': 'Срок хранения',
            'duration_unit': 'Единица измерения',
        }
    
    def __init__(self, *args, **kwargs):
        self.establishment = kwargs.pop('establishment', None)
        self.user = kwargs.pop('user', None)
        self.current_employee = kwargs.pop('current_employee', None)
        super().__init__(*args, **kwargs)
        
        # Фильтруем категории только для текущего заведения
        if self.establishment:
            self.fields['category'].queryset = Category.objects.filter(
                establishment=self.establishment, 
                is_active=True
            )
            self.fields['category'].empty_label = "Без категории"
        
        # Устанавливаем текущее время по умолчанию для ручного ввода
        if not self.instance.pk and not self.initial.get('manual_print_time'):
            tz = pytz.timezone(self.establishment.timezone) if self.establishment else pytz.UTC
            current_time = timezone.now().astimezone(tz)
            self.initial['manual_print_time'] = current_time.strftime('%Y-%m-%dT%H:%M')
        
        # Добавляем атрибут maxlength к полю name
        if 'name' in self.fields:
            self.fields['name'].max_length = 20  # Серверная валидация

    def clean_name(self):
        """Валидация названия продукта - не более 15 символов"""
        name = self.cleaned_data.get('name')
        if name and len(name) > 20:
            raise forms.ValidationError('Название продукта не может превышать 15 символов')
        return name

    def clean(self):
        cleaned_data = super().clean()
        use_manual_time = cleaned_data.get('use_manual_time')
        manual_print_time = cleaned_data.get('manual_print_time')
        
        if use_manual_time and not manual_print_time:
            self.add_error('manual_print_time', 'Укажите время маркировки при включении ручного режима')
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Если ручной режим не выбран, очищаем поле
        if not self.cleaned_data.get('use_manual_time'):
            instance.manual_print_time = None
            
        # Автоматически назначаем текущего сотрудника
        if self.current_employee:
            instance.employee = self.current_employee
            
        if self.establishment:
            instance.establishment = self.establishment
        if self.user:
            instance.user = self.user
            
        if commit:
            instance.save()
        return instance

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name', 'position']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Иван Иванов',
                'maxlength': '15'  # Добавляем ограничение для имени сотрудника
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Повар, Администратор'
            }),
        }
        labels = {
            'name': 'Имя сотрудника',
            'position': 'Должность (необязательно)',
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and len(name) > 30:
            raise forms.ValidationError('Имя сотрудника не может превышать 15 символов')
        return name

# Остальные формы остаются без изменений
class EstablishmentForm(forms.ModelForm):
    timezone = forms.ChoiceField(
        choices=[
            ('Europe/Moscow', 'Москва (MSK)'),
            ('Europe/Kaliningrad', 'Калининград (UTC+2)'),
            ('Europe/Samara', 'Самара (UTC+4)'),
            ('Asia/Yekaterinburg', 'Екатеринбург (UTC+5)'),
            ('Asia/Omsk', 'Омск (UTC+6)'),
            ('Asia/Krasnoyarsk', 'Красноярск (UTC+7)'),
            ('Asia/Irkutsk', 'Иркутск (UTC+8)'),
            ('Asia/Yakutsk', 'Якутск (UTC+9)'),
            ('Asia/Vladivostok', 'Владивосток (UTC+10)'),
            ('Asia/Magadan', 'Магадан (UTC+11)'),
            ('Asia/Kamchatka', 'Камчатка (UTC+12)'),
        ],
        initial='Europe/Moscow',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Часовой пояс'
    )
    
    class Meta:
        model = Establishment
        fields = ['name', 'timezone']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название вашего заведения (кафе, ресторан, магазин)',
                'maxlength': '30'  # Для названия заведения можно больше
            }),
        }

class JoinEstablishmentForm(forms.Form):
    invite_code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите код приглашения'
        })
    )

class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'style': 'width: 80px;'
        })
    )