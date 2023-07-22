from django.contrib import admin
from .models import CustomUser, Production, Task, Job, JobSite, Unit, ProductionTask
from django.contrib.auth.admin import UserAdmin
# Register your models here.

class ProductionTaskTimeInline(admin.TabularInline):
    model = ProductionTask
    extra = 1
    min_num = 1

@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    inlines = [ProductionTaskTimeInline]

class CustomUserAdmin(UserAdmin):
    pass

admin.site.register(CustomUser, CustomUserAdmin) 
admin.site.register(Task) 
admin.site.register(Job) 
admin.site.register(JobSite) 
admin.site.register(Unit)