from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from datetime import timedelta

class Establishment(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название заведения")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_establishments")
    created_at = models.DateTimeField(auto_now_add=True)
    invite_code = models.CharField(max_length=10, unique=True, blank=True)
    timezone = models.CharField(max_length=50, default='Europe/Moscow', verbose_name="Часовой пояс")
    block = models.BooleanField(default=True, blank=True, verbose_name='Активно(нет блокировки)')
    text_block_show = models.TextField(verbose_name='Текст предупреждения', blank=True, null=True)
    show_text = models.BooleanField(default=False, blank=True, verbose_name='Показывать текст?')

    paid_until = models.DateField(
        null=True, blank=True,
        verbose_name='Оплачено до',
        help_text='После этой даты заведение блокируется в приложении',
    )

    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = str(uuid.uuid4())[:8].upper()
        # Дефолт: при создании — сегодня + 1 месяц
        if self.paid_until is None:
            self.paid_until = (timezone.now().date() + timedelta(days=30))
        super().save(*args, **kwargs)

    def is_paid(self):
        """True, если подписка активна (оплачено до сегодня или позже)."""
        if self.paid_until is None:
            return True  # если поле не задано — не блокируем
        return self.paid_until >= timezone.now().date()

    def days_left(self):
        """Сколько дней осталось до блокировки. None, если не блокируется."""
        if self.paid_until is None:
            return None
        delta = (self.paid_until - timezone.now().date()).days
        return delta
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Заведение"
        verbose_name_plural = "Заведения"

class Employee(models.Model):
    """Сотрудники заведения (без регистрации в системе)"""
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, verbose_name="Заведение")
    name = models.CharField(max_length=100, verbose_name="Имя сотрудника")
    position = models.CharField(max_length=100, blank=True, verbose_name="Должность")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.establishment.name}"
    
    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        unique_together = ['establishment', 'name']

class EstablishmentMember(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Владелец'),
        ('manager', 'Управляющий'),
        ('worker', 'Сотрудник'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='worker')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'establishment']
        verbose_name = "Участник заведения"
        verbose_name_plural = "Участники заведений"

class Category(models.Model):
    """Категории продуктов"""
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, verbose_name="Заведение")
    name = models.CharField(max_length=100, verbose_name="Название категории")
    color = models.CharField(max_length=7, default='#6c757d', verbose_name="Цвет (HEX)")
    order = models.IntegerField(default=0, verbose_name="Порядок сортировки")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.establishment.name}"
    
    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        unique_together = ['establishment', 'name']
        ordering = ['order', 'name']


class ProductLabel(models.Model):
    DURATION_UNITS = [
        ('hours', 'часов'),
        ('days', 'суток'),
    ]
    
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, verbose_name="Заведение")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Создатель")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Маркировал сотрудник")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Категория")
    name = models.CharField(max_length=200, verbose_name="Название продукта")
    storage_temperature = models.CharField(max_length=50, verbose_name="Температура хранения", default="+4°C до +6°C")
    storage_duration = models.PositiveIntegerField(verbose_name="Срок хранения")
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNITS, default='hours', verbose_name="Единица измерения")
    manual_print_time = models.DateTimeField(null=True, blank=True, verbose_name="Ручное время печати")
    created_at = models.DateTimeField(auto_now_add=True)
    # Добавьте это поле в класс ProductLabel в models.py
    last_printed_at = models.DateTimeField(null=True, blank=True, verbose_name="Время последней печати")
    
    def __str__(self):
        return f"{self.name} - {self.establishment.name}"
    
    def get_storage_period_text(self):
        unit_text = 'час' if self.duration_unit == 'hours' else 'суток'
        if self.storage_duration % 10 == 1 and self.storage_duration % 100 != 11:
            unit_text += ''
        elif self.storage_duration % 10 in [2,3,4] and self.storage_duration % 100 not in [12,13,14]:
            unit_text += 'а' if self.duration_unit == 'hours' else ''
        else:
            unit_text += 'ов' if self.duration_unit == 'hours' else ''
        return f"{self.storage_duration} {unit_text}"
    
    def get_marking_person(self):
        """Возвращает имя того, кто маркировал продукт"""
        if self.employee:
            return self.employee.name
        return self.user.get_full_name() or self.user.username

    class Meta:
        verbose_name = "Маркировка продукта"
        verbose_name_plural = "Маркировки продуктов"

# Остальные модели (LabelCart, CartItem) остаются без изменений
class LabelCart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Корзина {self.user.username} - {self.establishment.name}"
    
    def get_total_labels(self):
        """Количество уникальных товаров"""
        return self.cart_items.count()
    
    def get_total_items_count(self):
        """Общее количество штук (сумма quantity)"""
        return sum(item.quantity for item in self.cart_items.all())
    
    def get_cart_count(self):
        """Для отображения в корзине - используем общее количество"""
        return self.get_total_items_count()
    

class CartItem(models.Model):
    cart = models.ForeignKey(LabelCart, on_delete=models.CASCADE, related_name='cart_items')
    label = models.ForeignKey(ProductLabel, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['cart', 'label']

class EmployeeSession(models.Model):
    """Сессия работы сотрудника"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, verbose_name="Заведение")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="Сотрудник")
    start_time = models.DateTimeField(auto_now_add=True, verbose_name="Время начала")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="Время окончания")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    
    def __str__(self):
        return f"{self.employee.name} - {self.establishment.name} ({self.start_time.date()})"
    
    class Meta:
        verbose_name = "Сессия сотрудника"
        verbose_name_plural = "Сессии сотрудников"





class ProductDelete(models.Model):
    """Модель для хранения удаленных/просроченных маркировок"""
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, verbose_name="Заведение")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Пользователь, который печатал")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Сотрудник")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Категория")
    
    name = models.CharField(max_length=200, verbose_name="Название продукта")
    storage_temperature = models.CharField(max_length=50, verbose_name="Температура хранения")
    storage_duration = models.PositiveIntegerField(verbose_name="Срок хранения")
    duration_unit = models.CharField(max_length=10, choices=ProductLabel.DURATION_UNITS, verbose_name="Единица измерения")
    
    created_at = models.DateTimeField(verbose_name="Время создания маркировки")
    printed_at = models.DateTimeField(verbose_name="Время печати")
    expiration_time = models.DateTimeField(verbose_name="Время истечения срока")
    deleted_at = models.DateTimeField(auto_now_add=True, verbose_name="Время удаления")
    
    # Связь с оригинальной маркировкой, если нужно
    original_label = models.ForeignKey(ProductLabel, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Оригинальная маркировка")
    
    def __str__(self):
        return f"{self.name} - истек {self.expiration_time}"
    
    def get_storage_period_text(self):
        unit_text = 'час' if self.duration_unit == 'hours' else 'суток'
        if self.storage_duration % 10 == 1 and self.storage_duration % 100 != 11:
            unit_text += ''
        elif self.storage_duration % 10 in [2,3,4] and self.storage_duration % 100 not in [12,13,14]:
            unit_text += 'а' if self.duration_unit == 'hours' else ''
        else:
            unit_text += 'ов' if self.duration_unit == 'hours' else ''
        return f"{self.storage_duration} {unit_text}"
    
    class Meta:
        verbose_name = "Просроченная маркировка"
        verbose_name_plural = "Просроченные маркировки"
        ordering = ['-expiration_time']


# для приложения 
# models.py
import secrets

class UserApiKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_key')
    key = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def get_or_create_for(user):
        obj, _ = UserApiKey.objects.get_or_create(
            user=user,
            defaults={'key': secrets.token_urlsafe(32)}
        )
        return obj

    @staticmethod
    def regenerate_for(user):
        obj, _ = UserApiKey.objects.get_or_create(user=user)
        obj.key = secrets.token_urlsafe(32)
        obj.save()
        return obj

    def __str__(self):
        return f"API key for {self.user.username}"



# models.py
class PrintJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('printing', 'Печатается'),
        ('done', 'Напечатано'),
        ('error', 'Ошибка'),
    ]

    establishment = models.ForeignKey(
        Establishment, on_delete=models.CASCADE,
        related_name='print_jobs',
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
    )
    label = models.ForeignKey(
        ProductLabel, on_delete=models.SET_NULL, null=True, blank=True,
    )

    payload = models.JSONField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending',
    )
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    printed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['establishment', 'status']),
        ]