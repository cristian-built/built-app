from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

class JobSite(models.Model):
    job_site_id = models.AutoField(primary_key=True)
    job_site_name = models.CharField(max_length=100)
    job_site_location = models.CharField(max_length=100)
    job_site_address = models.CharField(max_length=100)
    job_site_city = models.CharField(max_length=100)
    job_site_state = models.CharField(max_length=2)
    job_site_zipcode = models.CharField(max_length=10)
    def __str__(self):
        return f"{self.job_site_name}: {self.job_site_location}"

class Job(models.Model):
    job_id = models.AutoField(primary_key=True)
    job_name = models.CharField(max_length=100)
    job_site = models.ForeignKey(JobSite, on_delete=models.CASCADE)
    def __str__(self):
        return self.job_name

class Unit(models.Model):
    unit_id = models.AutoField(primary_key=True, blank=True)
    unit_name = models.CharField(max_length=100)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    def __str__(self):
        return self.unit_name

class CustomUser(AbstractUser):
    user_id = models.AutoField(primary_key=True)
    role = models.CharField(max_length=100)
    access = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()

class Task(models.Model):
    task_id = models.AutoField(primary_key=True, blank=True)
    task_name = models.CharField(max_length=100)
    def __str__(self):
        return self.task_name


class ProductionTask(models.Model):
    production = models.ForeignKey('Production', on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    task_time = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

class Production(models.Model):
    entry_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True)
    entry_date = models.DateField()
    updated_date = models.DateTimeField(auto_now=True)
    notes = models.TextField(null=True, blank=True)
    units = models.ManyToManyField(Unit, through=ProductionTask)
    tasks = models.ManyToManyField(Task, through=ProductionTask)
    def __str__(self):
        return f"{self.user_id}: {self.entry_date}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Perform the validation after saving the Production object
        if self.tasks.count() != self.productiontask_set.count():
            raise ValidationError("Number of selected tasks must match the number of tasktimes.")

        task_ids = self.tasks.values_list('task_id', flat=True)
        tasktime_ids = self.productiontask_set.values_list('task__task_id', flat=True)
        if set(task_ids) != set(tasktime_ids):
            raise ValidationError("Selected tasks must match the associated tasktimes.")
        
        # Save the related units and tasks
        for unit in self.units.all():
            ProductionTask.objects.create(production=self, unit=unit)

        for task in self.tasks.all():
            ProductionTask.objects.create(production=self, task=task)