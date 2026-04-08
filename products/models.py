from django.db import models


class Category(models.Model):
    category_name = models.CharField(max_length=255)
    description   = models.TextField(blank=True, null=True)
    is_active     = models.BooleanField(default=True)
    is_deleted    = models.BooleanField(default=False)

    def __str__(self):
        return self.category_name

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'


class Product(models.Model):
    product_name = models.CharField(max_length=255)
    description  = models.TextField(blank=True, null=True)
    category     = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    is_deleted   = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name

    class Meta:
        db_table = 'products'


class ProductImage(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image_url  = models.ImageField(upload_to='products/images/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.product_name}"

    class Meta:
        db_table = 'product_images'


class Variant(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku        = models.CharField(max_length=100, unique=True)
    size       = models.CharField(max_length=20)
    color      = models.CharField(max_length=50)
    price      = models.DecimalField(max_digits=10, decimal_places=2)
    stock      = models.IntegerField(default=0)
    is_active  = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.product_name} - {self.size} / {self.color}"

    class Meta:
        db_table = 'variants'


class VariantImage(models.Model):
    variant    = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name='images')
    image_url  = models.ImageField(upload_to='variants/images/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for variant {self.variant.sku}"

    class Meta:
        db_table = 'variant_images'