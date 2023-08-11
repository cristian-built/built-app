# context_processors.py
def custom_context(request):
    is_manager = request.user.groups.filter(name='Manager').exists()
    return {
        'is_manager': is_manager,
    }
