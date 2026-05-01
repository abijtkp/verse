from django.db import models


class Category(models.Model):
    category_name = models.CharField(max_length=255)
    description   = models.TextField(blank=True, null=True)
    is_active     = models.BooleanField(default=True)
    is_deleted    = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.category_name

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['-created_at']
        

class Product(models.Model):
    product_name = models.CharField(max_length=255)
    description  = models.TextField(blank=True, null=True)
    category     = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    is_active    = models.BooleanField(default=True)
    is_deleted   = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']


class ProductImage(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image_url  = models.ImageField(upload_to='products/images/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.product_name}"

    class Meta:
        db_table = 'product_images'
        ordering = ['-created_at']


class ColorVariant(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='color_variants')
    color_name = models.CharField(max_length=50)
    color_code = models.CharField(max_length=20, blank=True, null=True, help_text="Optional hex code, example: #000000")
    is_active  = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.product_name} - {self.color_name}"

    class Meta:
        db_table = 'color_variants'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'color_name'],
                name='unique_color_per_product'
            )
        ]
        
        
class ColorVariantImage(models.Model):
    color_variant    = models.ForeignKey(ColorVariant, on_delete=models.CASCADE, related_name='images')
    image_url  = models.ImageField(upload_to='products/color_variants/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for variant {self.color_variant.product.product_name} - {self.color_variant.color_name}"

    class Meta:
        db_table = 'color_variant_images'
        ordering = ['-created_at']
        

class SizeVariant(models.Model):
    color_variant = models.ForeignKey(ColorVariant, on_delete=models.CASCADE, related_name='size_variants')
    sku = models.CharField(max_length=100, unique=True)
    size = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        product_name = self.color_variant.product.product_name
        color_name = self.color_variant.color_name
        return f"{product_name} - {color_name} / {self.size}" 
    
    class Meta:
        db_table = 'size_variants'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['color_variant', 'size'],
                name='unique_size_per_color_variant'
            )
        ]
              