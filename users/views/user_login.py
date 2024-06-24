from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect


def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.user_type == 'technician':
                return redirect('technician:stats')
            elif user.user_type == 'workshop':
                return redirect('workshop:stats')
        else:
            return render(request, 'users/login/index.html', {'error': 'Invalid username or password'})
    else:
        return render(request, 'users/login/index.html')