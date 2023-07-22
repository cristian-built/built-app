from django import template
from django.db.models import Q, Count
from ..models import Production, ProductionTask, Job, Task

register = template.Library()

@register.filter
def unique_values(queryset, field_name):
    values = queryset.order_by(field_name).values_list(field_name, flat=True)
    print(values)  # Add this line for debugging
    distinct_values = values.distinct()
    print(distinct_values)  # Add this line for debugging
    return distinct_values

@register.filter
def calculate_total_task_time(production):
    total_time = 0
    for production_task in production.productiontask_set.all():
        total_time += production_task.task_time
    return total_time

@register.filter
def filter_productions(productions, users, start_date, end_date):
    return productions.filter(user__in=users, entry_date__range=[start_date, end_date])

@register.filter
def filter_production_tasks(production_tasks, productions, tasks, jobs):
    return production_tasks.filter(production__in=productions, task__in=tasks, unit__job__in=jobs)

@register.filter
def get_unique_jobs(production_tasks):
    return Job.objects.filter(unit__productiontask__in=production_tasks).distinct()

@register.filter
def get_unique_tasks(production_tasks):
    return Task.objects.filter(productiontask__in=production_tasks).distinct()

@register.filter
def calculate_days_worked(productions):
    return productions.annotate(production_count=Count("entry_date", filter=Q(productiontask__task_time__gt=0))).distinct().count()