from django.shortcuts import render


def custom_404(request, exception):
    if request.path.startswith("/adminpanel/"):
        return render(request, "adminpanel/404.html", status=404)

    return render(request, "404.html", status=404)