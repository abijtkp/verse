from decimal import Decimal
from datetime import datetime, time

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from adminpanel.views.core_views import admin_required
from offers.models import ProductOffer, CategoryOffer
from products.models import Product, Category


def _parse_offer_form(request):
    return {
        "offer_name": request.POST.get("offer_name", "").strip(),
        "offer_type": request.POST.get("offer_type", "").strip(),
        "product": request.POST.get("product", "").strip(),
        "category": request.POST.get("category", "").strip(),
        "discount_type": request.POST.get("discount_type", "").strip(),
        "discount_value": request.POST.get("discount_value", "").strip(),
        "maximum_discount_amount": request.POST.get("maximum_discount_amount", "").strip(),
        "valid_from": request.POST.get("valid_from", "").strip(),
        "valid_to": request.POST.get("valid_to", "").strip(),
        "is_active": request.POST.get("is_active") == "on",
    }


def _validate_offer_form(form_data):
    field_errors = {}

    if not form_data["offer_name"]:
        field_errors["offer_name"] = "Offer name is required."

    if form_data["offer_type"] not in ["product", "category"]:
        field_errors["offer_type"] = "Select product or category."

    product = None
    category = None

    if form_data["offer_type"] == "product":
        product = Product.objects.filter(
            id=form_data["product"],
            is_active=True,
            is_deleted=False
        ).first()

        if not product:
            field_errors["product"] = "Select a valid product."

    if form_data["offer_type"] == "category":
        category = Category.objects.filter(
            id=form_data["category"],
            is_active=True,
            is_deleted=False
        ).first()

        if not category:
            field_errors["category"] = "Select a valid category."

    if form_data["discount_type"] not in ["percentage", "flat"]:
        field_errors["discount_type"] = "Select a valid discount type."

    discount_value = Decimal("0.00")
    try:
        discount_value = Decimal(form_data["discount_value"])

        if discount_value <= 0:
            field_errors["discount_value"] = "Discount must be greater than 0."

        if form_data["discount_type"] == "percentage" and discount_value > 90:
            field_errors["discount_value"] = "Discount cannot exceed 90%."

    except:
        field_errors["discount_value"] = "Enter a valid discount value."

    maximum_discount_obj = None

    if form_data["discount_type"] == "percentage" and form_data["maximum_discount_amount"]:
        try:
            maximum_discount_obj = Decimal(form_data["maximum_discount_amount"])

            if maximum_discount_obj <= 0:
                field_errors["maximum_discount_amount"] = "Maximum discount must be greater than 0."

        except:
            field_errors["maximum_discount_amount"] = "Enter a valid maximum discount amount."

    valid_from_obj = None
    valid_to_obj = None

    try:
        valid_from_date = datetime.strptime(form_data["valid_from"], "%Y-%m-%d").date()
        valid_from_obj = timezone.make_aware(datetime.combine(valid_from_date, time.min))
    except:
        field_errors["valid_from"] = "Enter a valid start date."

    try:
        valid_to_date = datetime.strptime(form_data["valid_to"], "%Y-%m-%d").date()
        valid_to_obj = timezone.make_aware(datetime.combine(valid_to_date, time.max))
    except:
        field_errors["valid_to"] = "Enter a valid expiry date."

    if valid_from_obj and valid_to_obj and valid_to_obj <= valid_from_obj:
        field_errors["valid_to"] = "Expiry date must be after start date."

    return {
        "field_errors": field_errors,
        "product": product,
        "category": category,
        "discount_value": discount_value,
        "maximum_discount_obj": maximum_discount_obj,
        "valid_from_obj": valid_from_obj,
        "valid_to_obj": valid_to_obj,
    }


@admin_required
def offer_list_view(request):
    search_query = request.GET.get("q", "").strip()

    product_offers = ProductOffer.objects.select_related(
        "product",
        "product__category"
    )

    category_offers = CategoryOffer.objects.select_related("category")

    offers = []

    for offer in product_offers:
        offers.append({
            "id": offer.id,
            "offer_type": "product",
            "offer_name": offer.offer_name,
            "target_name": offer.product.product_name,
            "discount_type": offer.discount_type,
            "discount_value": offer.discount_value,
            "maximum_discount_amount": offer.maximum_discount_amount,
            "valid_from": offer.valid_from,
            "valid_to": offer.valid_to,
            "is_active": offer.is_active,
            "created_at": offer.created_at,
        })

    for offer in category_offers:
        offers.append({
            "id": offer.id,
            "offer_type": "category",
            "offer_name": offer.offer_name,
            "target_name": offer.category.category_name,
            "discount_type": offer.discount_type,
            "discount_value": offer.discount_value,
            "maximum_discount_amount": offer.maximum_discount_amount,
            "valid_from": offer.valid_from,
            "valid_to": offer.valid_to,
            "is_active": offer.is_active,
            "created_at": offer.created_at,
        })

    if search_query:
        offers = [
            offer for offer in offers
            if search_query.lower() in offer["offer_name"].lower()
            or search_query.lower() in offer["target_name"].lower()
            or search_query.lower() in offer["offer_type"].lower()
        ]

    offers = sorted(offers, key=lambda item: item["created_at"], reverse=True)

    paginator = Paginator(offers, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "adminpanel/offers/offer_list.html", {
        "page_obj": page_obj,
        "search_query": search_query,
    })


@admin_required
def add_offer_view(request):
    field_errors = {}
    form_data = {}

    products = Product.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by("product_name")

    categories = Category.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by("category_name")

    if request.method == "POST":
        form_data = _parse_offer_form(request)
        result = _validate_offer_form(form_data)
        field_errors = result["field_errors"]

        if not field_errors:
            if form_data["offer_type"] == "product":
                ProductOffer.objects.create(
                    offer_name=form_data["offer_name"],
                    product=result["product"],
                    discount_type=form_data["discount_type"],
                    discount_value=result["discount_value"],
                    maximum_discount_amount=result["maximum_discount_obj"],
                    valid_from=result["valid_from_obj"],
                    valid_to=result["valid_to_obj"],
                    is_active=form_data["is_active"],
                )
            else:
                CategoryOffer.objects.create(
                    offer_name=form_data["offer_name"],
                    category=result["category"],
                    discount_type=form_data["discount_type"],
                    discount_value=result["discount_value"],
                    maximum_discount_amount=result["maximum_discount_obj"],
                    valid_from=result["valid_from_obj"],
                    valid_to=result["valid_to_obj"],
                    is_active=form_data["is_active"],
                )

            messages.success(request, "Offer created successfully.")
            return redirect("offer_list")

        messages.error(request, "Please correct the errors below.")

    return render(request, "adminpanel/offers/add_offer.html", {
        "products": products,
        "categories": categories,
        "field_errors": field_errors,
        "form_data": form_data,
    })


@admin_required
def edit_offer_view(request, offer_type, offer_id):
    if offer_type == "product":
        offer = get_object_or_404(ProductOffer, id=offer_id)
    elif offer_type == "category":
        offer = get_object_or_404(CategoryOffer, id=offer_id)
    else:
        messages.error(request, "Invalid offer type.")
        return redirect("offer_list")

    field_errors = {}
    form_data = {}

    products = Product.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by("product_name")

    categories = Category.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by("category_name")

    if request.method == "POST":
        form_data = _parse_offer_form(request)
        result = _validate_offer_form(form_data)
        field_errors = result["field_errors"]

        if not field_errors:
            offer.offer_name = form_data["offer_name"]
            offer.discount_type = form_data["discount_type"]
            offer.discount_value = result["discount_value"]
            offer.maximum_discount_amount = result["maximum_discount_obj"]
            offer.valid_from = result["valid_from_obj"]
            offer.valid_to = result["valid_to_obj"]
            offer.is_active = form_data["is_active"]

            if form_data["offer_type"] == "product":
                if offer_type == "category":
                    offer.delete()
                    ProductOffer.objects.create(
                        offer_name=form_data["offer_name"],
                        product=result["product"],
                        discount_type=form_data["discount_type"],
                        discount_value=result["discount_value"],
                        maximum_discount_amount=result["maximum_discount_obj"],
                        valid_from=result["valid_from_obj"],
                        valid_to=result["valid_to_obj"],
                        is_active=form_data["is_active"],
                    )
                else:
                    offer.product = result["product"]
                    offer.save()

            elif form_data["offer_type"] == "category":
                if offer_type == "product":
                    offer.delete()
                    CategoryOffer.objects.create(
                        offer_name=form_data["offer_name"],
                        category=result["category"],
                        discount_type=form_data["discount_type"],
                        discount_value=result["discount_value"],
                        maximum_discount_amount=result["maximum_discount_obj"],
                        valid_from=result["valid_from_obj"],
                        valid_to=result["valid_to_obj"],
                        is_active=form_data["is_active"],
                    )
                else:
                    offer.category = result["category"]
                    offer.save()

            messages.success(request, "Offer updated successfully.")
            return redirect("offer_list")

        messages.error(request, "Please correct the errors below.")

    initial_offer_type = offer_type
    initial_target_id = offer.product.id if offer_type == "product" else offer.category.id

    return render(request, "adminpanel/offers/edit_offer.html", {
        "offer": offer,
        "offer_type": offer_type,
        "initial_offer_type": initial_offer_type,
        "initial_target_id": initial_target_id,
        "products": products,
        "categories": categories,
        "field_errors": field_errors,
        "form_data": form_data,
    })


@admin_required
def toggle_offer_status_view(request, offer_type, offer_id):
    if request.method != "POST":
        return redirect("offer_list")

    if offer_type == "product":
        offer = get_object_or_404(ProductOffer, id=offer_id)
    elif offer_type == "category":
        offer = get_object_or_404(CategoryOffer, id=offer_id)
    else:
        messages.error(request, "Invalid offer type.")
        return redirect("offer_list")

    offer.is_active = not offer.is_active
    offer.save(update_fields=["is_active", "updated_at"])

    messages.success(request, "Offer status updated successfully.")
    return redirect("offer_list")