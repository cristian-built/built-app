from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse, reverse_lazy
from django.views import generic

from .models import Production, ProductionTask, Job, Unit, Task, CustomUser
from django.utils import timezone
from django.utils.html import escape
from .forms import ProductionForm, ProductionTaskFormSet
from django.forms import formset_factory
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView

from django.utils.timezone import timedelta
from django.utils import timezone

import plotly.graph_objects as go
from plotly.offline import plot
import plotly.express as px

import pandas as pd
from .models import ProductionTask

from datetime import datetime, date, timedelta


# Functions

def format_date(row, col, format="%a, %B %d, %Y"):
    return row[col].strftime(format)

def combine_2_string_cols(row, col1, col2):
    return f"{row[col1]} {row[col2]}"



class DashboardView(LoginRequiredMixin, generic.ListView):
    model = Production
    template_name = "production_tracker/dashboard.html"
    context_object_name = "production_list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Set default values for filter parameters
        default_start_date = date.today() - timedelta(days=7)
        default_end_date = date.today()

        # Get the filter parameters from the request or use default values
        users = self.request.GET.getlist("users")
        jobs = self.request.GET.getlist("jobs")
        tasks = self.request.GET.getlist("tasks")
        units = self.request.GET.getlist("units")
        start_date = self.request.GET.get("start_date", default_start_date)
        end_date = self.request.GET.get("end_date", default_end_date)

        # Convert start_date and end_date strings to date objects
        start_date = datetime.strptime(f"{start_date}", "%Y-%m-%d").date()
        end_date = datetime.strptime(f"{end_date}", "%Y-%m-%d").date()

        # Check if the filter parameters are empty, if so, use the default values
        if not users:
            users = CustomUser.objects.all()
            print(users)
        else:
            users = CustomUser.objects.filter(pk__in=users)
            print(users)
        if not jobs:
            jobs = Job.objects.all()
            print(jobs)
        else:
            jobs = Job.objects.filter(job_id__in=jobs)
            print(jobs)
        if not tasks:
            tasks = Task.objects.all()
            print(tasks)
        else:
            tasks = Task.objects.filter(task_id__in=tasks)
            print(tasks)
        if not units:
            units = Unit.objects.all()
            print(units)
        else:
            units = Unit.objects.filter(unit_id__in=units)
            print(units)
        
        # Apply filters to the Production and ProductionTask objects
        productions = Production.objects.filter(
            entry_date__range=[start_date, end_date],
            user__in=users
        )
        production_tasks = ProductionTask.objects.filter(
            production__in=productions,
            task__in=tasks,
            unit__in=units
        )

        # Convert the queryset to a list of dictionaries
        # data = list(job_distribution.values())
        production_data = list(productions.values())
        data = list(production_tasks.values())

        # Create a DataFrame from the data
        df = pd.DataFrame(data)
        

        if 'production_id' in df:
            production_df = pd.DataFrame(production_data)
            production_df = production_df[production_df['entry_id'].isin(df['production_id'].unique())].reset_index()
        else:
            production_df = pd.DataFrame()

        tasks_df = pd.DataFrame(list(Task.objects.all().values()))
        context["tasks_df"] = tasks_df.to_html()

        units_df = pd.DataFrame(list(Unit.objects.all().values()))
        context["units_df"] = units_df.to_html()

        users_df = pd.DataFrame(list(CustomUser.objects.all().values()))
        users_df = users_df[['user_id', 'username', 'first_name', 'last_name']]
        context["users_df"] = users_df.to_html()

        if df.empty or production_df.empty:
            context["merged_df"] = "No Data"
            context['fig1'] = "No Data"
            context['units_worked_df'] = "No Data"
        else:
            merged_df = pd.merge(pd.merge(df, production_df.rename(columns={"entry_id":"production_id"})), tasks_df, how="left", on="task_id")
            days_worked_df = pd.DataFrame(merged_df.groupby(['entry_date', 'task_name'])['task_time'].sum()).reset_index()
            context["merged_df"] = merged_df.to_html()

            # Assuming you have the DataFrame named 'merged_df' containing the data
            # Convert the 'entry_date' column to datetime type if it's not already in datetime format
            days_worked_df['entry_date'] = pd.to_datetime(days_worked_df['entry_date'])

            #Days Worked
            days_worked_df = pd.DataFrame(days_worked_df.copy().groupby('entry_date')['task_time'].sum()).reset_index()
            days_worked_df['entry_date'] = days_worked_df.apply(lambda row: format_date(row, col='entry_date'), axis=1)
            days_worked_df = days_worked_df.reset_index()
            context['days_worked_df'] = dict(zip(list(days_worked_df['entry_date']),list(days_worked_df['task_time'])))
            
            # Persons Worked 
            persons_worked_df = pd.merge(merged_df, users_df, how="left", on="user_id")
            persons_worked_df['Name'] = persons_worked_df.apply(lambda row: combine_2_string_cols(row, 'first_name', 'last_name'), axis=1)
            persons_worked_df = pd.DataFrame(persons_worked_df.groupby('entry_date')['Name'].unique()).reset_index()
            context['persons_worked_df'] = persons_worked_df

            # Units Worked
            units_worked_df = pd.merge(merged_df, units_df, how="left", on="unit_id")
            units_worked_df = pd.DataFrame(units_worked_df.groupby(['entry_date'])['unit_name'].unique()).reset_index()
            context['units_worked_df'] = units_worked_df

            # Create a line chart using Plotly
            line_chart_df = merged_df.copy()
            line_chart_df = pd.DataFrame(line_chart_df.groupby(['entry_date', 'task_name'])['task_time'].sum()).reset_index()
            fig1 = px.line(line_chart_df, x='entry_date', y='task_time', color='task_name', title='Production Task Line Chart')
            fig1.update_traces(mode='lines+markers')
            fig1.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
                )

            # Show the chart
            context['fig1'] = plot(fig1, output_type="div")

            # Create a Stacked Bar Chart
            bar_chart_df = merged_df.copy()
            bar_chart_df = pd.merge(merged_df, units_df, how="left", on="unit_id")
            bar_chart_df = pd.DataFrame(bar_chart_df.groupby(["unit_name", "task_name"])["task_time"].sum()).reset_index()
            fig2 = px.bar(bar_chart_df, x="unit_name", y="task_time", color="task_name", title="Production Tasks Bar Chart")
            fig2.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
                )
            context['fig2'] = plot(fig2, output_type="div")
            context["bar_chart_df"] = bar_chart_df.to_html()


        context["users"] = CustomUser.objects.all()
        context["jobs"] = Job.objects.all()
        context["tasks"] = Task.objects.all()
        context["units"] = Unit.objects.all()
        context["start_date"] = start_date.strftime("%Y-%m-%d")  # Update the start_date format
        context["end_date"] = end_date.strftime("%Y-%m-%d")  # Update the end_date format
        
        if df.empty:
            context["fig"] = "No data is available with these filter selections."
            context["total_task_time"] = None
            context['units_worked'] = None
        else:
            pie_df = pd.merge(df, tasks_df, how="left", on='task_id')
            task_time_df = pie_df.groupby('task_name')['task_time'].sum().to_dict()
            context['task_time_df'] = task_time_df
            fig = px.pie(pie_df, values='task_time', names='task_name', title="Production Task Pie Chart")
            context["fig"] = plot(fig, output_type="div")
            html_table = pie_df.to_html()
            context['html_table'] = html_table
            context["total_task_time"] = df['task_time'].sum()
            context['units_worked'] = len(df['unit_id'].unique())
            

        if production_df.empty:
            context["prod_df"] = "No Production Data with these filter selections."
            context["days_worked"] = None
            context["unique_users"] = None
            
        else:
            context["days_worked"] = len(production_df['entry_date'].unique())
            context["unique_users"] = len(production_df['user_id'].unique())
            production_df = production_df.to_html()
            context["prod_df"] = production_df
            
            
        return context



class IndexView(LoginRequiredMixin, generic.ListView):
    template_name = "production_tracker/index.html"
    context_object_name = "todays_productions_list"

    def get_queryset(self):
        return Production.objects.filter(user=self.request.user, entry_date__lte=timezone.now()).order_by("-entry_date")[:10]
    
class DetailView(LoginRequiredMixin, generic.DetailView):
    model = Production
    template_name = "production_tracker/detail.html"

    def get_queryset(self):
        return Production.objects.filter(entry_date__lte=timezone.now())

class ProductionCreateView(LoginRequiredMixin, CreateView):
    model = Production
    form_class = ProductionForm
    template_name = 'production_tracker/create.html'
    success_url = reverse_lazy('production_tracker:index')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = ProductionTaskFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = ProductionTaskFormSet(instance=self.object)
        form = context['form']
        form.formset = context['formset']  # Set the formset attribute
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            self.object = form.save(commit=False)
            self.object.user = self.request.user
            self.object.save()
            formset.instance = self.object
            formset.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            print(formset.errors)  # Print the formset errors for debugging
            return self.render_to_response(self.get_context_data(form=form))


# # class ProductionUpdateView(generic.UpdateView):
# #     model = Production
# #     form_class = ProductionForm
# #     template_name = 'production_tracker/update.html'
# #     success_url = reverse_lazy('production_tracker:index')

# #     def get_context_data(self, **kwargs):
# #         context = super().get_context_data(**kwargs)
# #         if self.request.POST:
# #             context['formset'] = ProductionTaskFormSet(self.request.POST, instance=self.object)
# #         else:
# #             context['formset'] = ProductionTaskFormSet(instance=self.object)
# #         return context

# #     def form_valid(self, form):
# #         context = self.get_context_data()
# #         formset = context['formset']
# #         if formset.is_valid():
# #             self.object = form.save()
# #             formset.instance = self.object
# #             formset.save()
# #             return redirect(self.get_success_url())
# #         else:
# #             print(formset.errors)  # Print the formset errors for debugging
# #             return self.render_to_response(self.get_context_data(form=form))