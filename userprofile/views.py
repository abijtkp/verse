from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def profile_view(request):
    profile = request.user.userprofile
    addresses = request.user.addresses.all()

    return render(request, 'userprofile/profile.html', {
        'profile': profile,
        'addresses': addresses
    })
    
@login_required
def address_list(request):
    addresses = request.user.addresses.all()

    return render(request, 'userprofile/address_list.html', {
        'addresses': addresses
    })    
 
@login_required
def edit_profile_view(request):
    user = request.user

    if request.method == 'POST':
        user.full_name = request.POST.get('full_name')
        user.phone_number = request.POST.get('phone_number')
        user.save()
        return redirect('profile')

    return render(request, 'userprofile/edit_profile.html', {
        'user': user
    })   