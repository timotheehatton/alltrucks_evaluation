from django.contrib.auth import authenticate, get_user_model, login
from django.shortcuts import redirect, render


def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        print(email, password)
        try:
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                if user.user_type == 'technician':
                    return redirect('technician:stats')
                elif user.user_type == 'manager':
                    return redirect('workshop:stats')
        except:
            pass
        return render(request, 'users/login/index.html', {'error': 'Invalid email or password'})
    else:
        return render(request, 'users/login/index.html')