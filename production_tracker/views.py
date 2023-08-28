from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse, reverse_lazy
from django.views import generic, View

from .models import Production, ProductionTask, Job, Unit, Task, CustomUser
from django.utils import timezone
from django.utils.html import escape
from .forms import ProductionForm, ProductionTaskFormSet
from django.forms import formset_factory
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic.edit import CreateView
from django.template.loader import get_template

from django.utils.timezone import timedelta
from django.utils import timezone

import plotly.graph_objects as go
from plotly.offline import plot
import plotly.express as px

import pandas as pd
from .models import ProductionTask, Production
from datetime import datetime, date, timedelta


# # Functions

# def generate_pdf(request):
#     response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
#     response['Content-Disposition'] = 'attachment; filename="productions.xlsx"'

#     # Create a new Excel workbook and add a worksheet
#     output = io.BytesIO()
#     workbook = xlsxwriter.Workbook(output)
#     worksheet = workbook.add_worksheet()

#     # Add a bold format to use to highlight cells
#     bold = workbook.add_format({'bold': True})

#     # Write the table headers
#     headers = ['User', 'Date', 'Notes', 'Unit', 'Task & Tasktime']
#     for col_num, header in enumerate(headers):
#         worksheet.write(0, col_num, header, bold)

#     # Write data from the table
#     row = 1
#     for production in Production.objects.all():
#         for task in production.productiontask_set.all():
#             worksheet.write(row, 0, f"{production.user.first_name} {production.user.last_name}")
#             worksheet.write(row, 1, production.entry_date.strftime('%Y-%m-%d'))
#             worksheet.write(row, 2, production.notes)
#             worksheet.write(row, 3, task.unit.unit_name)
#             worksheet.write(row, 4, f"{task.task.task_name}: {task.task_time}")
#             row += 1

#     # Close the workbook and return the response
#     workbook.close()
#     output.seek(0)
#     response.write(output.read())

#     return response

def format_date(row, col, format="%a, %B %d, %Y"):
    return row[col].strftime(format)

def combine_2_string_cols(row, col1, col2):
    return f"{row[col1]} {row[col2]}"



class DashboardView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):
    model = Production
    template_name = "production_tracker/dashboard.html"
    context_object_name = "production_list"

    def test_func(self):
        # Implement the test logic here
        return self.request.user.groups.filter(name='Manager').exists()

    def handle_no_permission(self):
        return HttpResponseRedirect(reverse('production_tracker:index'))  # Redirect to IndexView for non-manager users

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

    
class ProductionsListView(LoginRequiredMixin, generic.ListView):
    model = Production
    template_name = "production_tracker/productions_list.html"
    context_object_name = "productions"
    def test_func(self):
        # Implement the test logic here
        return self.request.user.groups.filter(name='Manager').exists()

    def handle_no_permission(self):
        return HttpResponseRedirect(reverse('production_tracker:index'))  # Redirect to IndexView for non-manager users
    
    def get_queryset(self):
        # Get start_date and end_date from query parameters
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        selected_users = self.request.GET.getlist("users")

        if not selected_users:
            selected_users = CustomUser.objects.filter(is_active=True)
        else:
            selected_users = CustomUser.objects.filter(pk__in=selected_users)
        print(selected_users)

        # If start_date is not provided, set a default value (7 days ago)
        if not start_date:
            default_start_date = timezone.now().date() - timedelta(days=7)
            start_date = default_start_date.strftime("%Y-%m-%d")

        # If end_date is not provided, set a default value (today)
        if not end_date:
            default_end_date = timezone.now().date()
            end_date = default_end_date.strftime("%Y-%m-%d")

        # Convert start_date and end_date strings to date objects
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Filter productions based on the selected date range and users
        queryset = Production.objects.filter(
            user__in=selected_users,
            entry_date__range=[start_date, end_date]
        ).order_by("user", "entry_date")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Set default values for filter parameters
        default_start_date = date.today() - timedelta(days=7)
        default_end_date = date.today()

        # Check if the filter parameters are empty, if so, use the default values
        selected_users = self.request.GET.getlist("users")
        if not selected_users:
            selected_users = CustomUser.objects.filter(is_active=True)
        else:
            selected_users = CustomUser.objects.filter(pk__in=selected_users)

        jobs = self.request.GET.getlist("jobs")
        tasks = self.request.GET.getlist("tasks")
        units = self.request.GET.getlist("units")
        start_date = self.request.GET.get("start_date", default_start_date)
        end_date = self.request.GET.get("end_date", default_end_date)

        # Convert start_date and end_date strings to date objects
        start_date = datetime.strptime(f"{start_date}", "%Y-%m-%d").date()
        end_date = datetime.strptime(f"{end_date}", "%Y-%m-%d").date()

        # Check if the filter parameters are empty, if so, use the default values
        users = CustomUser.objects.all()
        if not jobs:
            jobs = Job.objects.all()
        else:
            jobs = Job.objects.filter(job_id__in=jobs)
        if not tasks:
            tasks = Task.objects.all()
        else:
            tasks = Task.objects.filter(task_id__in=tasks)
        if not units:
            units = Unit.objects.all()
        else:
            units = Unit.objects.filter(unit_id__in=units)

        users_df = pd.DataFrame(list(CustomUser.objects.all().values()))
        users_df = users_df[['user_id', 'username', 'first_name', 'last_name']]
        users_df['Name'] = users_df.apply(lambda row: combine_2_string_cols(row, 'first_name', 'last_name'), axis=1)

        tasks_df = pd.DataFrame(list(Task.objects.all().values()))[['task_id', 'task_name']]
        context["tasks_df"] = tasks_df.to_html()

        units_df = pd.DataFrame(list(Unit.objects.all().values()))[['unit_id', 'unit_name']]
        context["units_df"] = units_df.to_html()
        
        productions = Production.objects.filter(
            user__in=selected_users,
            entry_date__range=[start_date, end_date]
        ).order_by("user", "entry_date")

        productions_data = list(productions.values())

        productions_data_df = pd.DataFrame(productions_data)

        production_tasks = ProductionTask.objects.filter(
            production__in=productions,
        )
        production_tasks_data = list(production_tasks.values())
        production_tasks_data_df = pd.DataFrame(production_tasks_data)

        if production_tasks_data_df.empty or productions_data_df.empty:
            context["p_df"] = '<span class="d-block p-2 text-center my-3 text-bg-dark">"No data to display."</span>'
            context["daily_report_by_unit"] = '<span class="d-block p-2 text-center my-3 text-bg-dark">"No data to display."</span>'
        else:
            productions_merged_df = pd.merge(pd.merge(pd.merge(pd.merge(productions_data_df, production_tasks_data_df.rename(columns={'production_id':'entry_id'}), how='left', on='entry_id'), units_df, on='unit_id', how='left'), tasks_df, on='task_id', how='left'), users_df, on='user_id', how='left')
            productions_merged_df = productions_merged_df[['entry_date', 'Name', 'notes', 'unit_name', 'task_name', 'task_time']]
            productions_merged_df = productions_merged_df.rename(columns={
                'entry_date':'Date',  
                'notes':'Notes', 
                'unit_name':'Unit Name', 
                'task_name':'Task Name', 
                'task_time': 'Number of Hours'
            })

            p_df = pd.DataFrame(productions_merged_df.groupby(['Date','Name', 'Notes', 'Unit Name', 'Task Name'])['Number of Hours'].sum())

            daily_report_by_unit = productions_merged_df.copy()
            daily_report_by_unit = pd.DataFrame(daily_report_by_unit.groupby(['Unit Name', 'Date', 'Task Name'])[['Number of Hours', 'Notes']].sum())
            context["p_df"] = p_df.to_html(classes="table table-bordered border-dark").replace("<th", "<th class='align-middle' style='text-align:center;'").replace("<td", "<td class='align-middle' style='text-align:center;'")
            context["daily_report_by_unit"] = daily_report_by_unit.to_html(classes="table table-bordered border-dark").replace("<th", "<th class='align-middle' style='text-align:center;'").replace("<td", "<td class='align-middle' style='text-align:center;'")
        
        context["users"] = CustomUser.objects.all()
        context["selected_users"] = selected_users
        # context["jobs"] = jobs
        # context["tasks"] = tasks
        # context["units"] = units
        context["start_date"] = start_date.strftime("%Y-%m-%d")  # Update the start_date format
        context["end_date"] = end_date.strftime("%Y-%m-%d")  # Update the end_date format
        context["productions_data_df"] = productions_data_df.to_html()
        context["production_tasks_data_df"] = production_tasks_data_df.to_html()
        # context["productions_merged_df"] = productions_merged_df.to_html()


        # Set the active tab based on the URL
        if self.request.path == reverse('production_tracker:dailies'):
            context['active_tab'] = 'dailies'
        else:
            context['active_tab'] = 'productions'
            
        return context

    # def generate_excel(self, data_frame):
    #     # Convert the DataFrame to an Excel file in-memory
    #     excel_file = io.BytesIO()
    #     excel_writer = pd.ExcelWriter(excel_file, engine='xlsxwriter')
    #     data_frame.to_excel(excel_writer, sheet_name='Sheet1', index=False)
    #     excel_writer.save()

    #     # Create the HttpResponse object with the appropriate headers
    #     response = HttpResponse(
    #         excel_file.getvalue(),
    #         content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    #     )
    #     response['Content-Disposition'] = 'attachment; filename=your_report.xlsx'
    #     return response
    
    # def get(self, request, *args, **kwargs):
    #     users_df = pd.DataFrame(list(CustomUser.objects.all().values()))
    #     users_df = users_df[['user_id', 'username', 'first_name', 'last_name']]
    #     users_df['Name'] = users_df.apply(lambda row: combine_2_string_cols(row, 'first_name', 'last_name'), axis=1)

    #     tasks_df = pd.DataFrame(list(Task.objects.all().values()))[['task_id', 'task_name']]

    #     units_df = pd.DataFrame(list(Unit.objects.all().values()))[['unit_id', 'unit_name']]

    #     # Check if the filter parameters are empty, if so, use the default values
    #     selected_users = self.request.GET.getlist("users")
    #     if not selected_users:
    #         selected_users = CustomUser.objects.filter(is_active=True)
    #     else:
    #         selected_users = CustomUser.objects.filter(pk__in=selected_users)

    #     # Apply filters to the Production and ProductionTask objects
    #     productions = Production.objects.filter(
    #         entry_date__range=[start_date, end_date],
    #         user__in=selected_users
    #     )
    #     production_tasks = ProductionTask.objects.filter(
    #         production__in=productions,
    #     )

    #     productions_data = list(productions.values())

    #     productions_data_df = pd.DataFrame(productions_data)

    #     production_tasks = ProductionTask.objects.filter(
    #         production__in=productions,
    #     )
    #     production_tasks_data = list(production_tasks.values())
    #     production_tasks_data_df = pd.DataFrame(production_tasks_data)

    #     productions_merged_df = pd.merge(pd.merge(pd.merge(pd.merge(productions_data_df, production_tasks_data_df.rename(columns={'production_id':'entry_id'}), how='left', on='entry_id'), units_df, on='unit_id', how='left'), tasks_df, on='task_id', how='left'), users_df, on='user_id', how='left')
    #     productions_merged_df = productions_merged_df[['entry_date', 'Name', 'notes', 'unit_name', 'task_name', 'task_time']]
    #     productions_merged_df = productions_merged_df.rename(columns={
    #         'entry_date':'Date',  
    #         'notes':'Notes', 
    #         'unit_name':'Unit Name', 
    #         'task_name':'Task Name', 
    #         'task_time': 'Number of Hours'
    #     })

    #     daily_report_by_unit = productions_merged_df.copy()
    #     daily_report_by_unit = pd.DataFrame(daily_report_by_unit.groupby(['Unit Name', 'Date', 'Task Name'])[['Number of Hours', 'Notes']].sum()).reset_index()

    #     if 'excel' in request.GET:
    #         # Recreate the DataFrame for the Excel export
    #         selected_users = self.request.GET.getlist("users")
    #         start_date = self.request.GET.get("start_date")
    #         end_date = self.request.GET.get("end_date")

    #         # Extract data and create the DataFrame similar to what you did in get_context_data
    #         # Make sure to apply necessary filtering and processing as needed
    #         daily_report_by_unit_data = daily_report_by_unit.copy()  # Replace this with the data extraction logic

    #         # Create the DataFrame
    #         daily_report_by_unit_df = pd.DataFrame(daily_report_by_unit_data)

    #         # Generate and return the Excel file response
    #         return self.generate_excel(daily_report_by_unit_df)

    #     return super().get(request, *args, **kwargs)



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
