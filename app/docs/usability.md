# Guía de Usabilidad - Ecommerce API

Esta guía describe cómo utilizar la API de comercio electrónico desde el punto de vista de un cliente (frontend, aplicación móvil u otro consumidor). No es necesario conocer la implementación interna: aquí se explica qué endpoints usar, en qué orden, qué datos enviar y cómo interpretar las respuestas.

---

## 1. Convenciones Generales

- **Base URL**: `http://localhost/api/v1` en desarrollo local con Docker.
- **Formato**: todas las solicitudes y respuestas son `application/json`, salvo webhooks y subida de archivos.
- **Autenticación**: la mayoría de endpoints requieren un **Bearer token** en el header:
  ```
  Authorization: Bearer <access_token>
  ```
- **Documentación interactiva**: navega a `/docs` (Swagger UI) o `/redoc` para probar endpoints.
- **Paginación**: el catálogo usa paginación por cursor. La respuesta incluye `next_cursor` cuando hay más resultados.
- **Errores**: respuestas con formato estándar:
  ```json
  {
    "detail": "Mensaje descriptivo del error"
  }
  ```

---

## 2. Autenticación

### 2.1. Registro de usuario

**Endpoint**: `POST /auth/register`

```json
{
  "email": "usuario@ejemplo.com",
  "password": "ContraseñaSegura123!",
  "full_name": "Juan Pérez"
}
```

**Respuesta**: `201 Created` con datos básicos del usuario.

**Importante**: después del registro se envía un email de verificación. La cuenta no puede realizar compras hasta verificarse.

### 2.2. Verificación de email

El email contiene un enlace o token. Envía el token al endpoint:

**Endpoint**: `POST /auth/verify-email`

```json
{
  "token": "<token_del_email>"
}
```

### 2.3. Inicio de sesión

**Endpoint**: `POST /auth/login`

```json
{
  "email": "usuario@ejemplo.com",
  "password": "ContraseñaSegura123!"
}
```

**Respuesta**: devuelve `access_token` en el body y `refresh_token` en una cookie `HttpOnly`.

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### 2.4. Refrescar access token

**Endpoint**: `POST /auth/refresh`

No es necesario enviar el refresh token manualmente: debe estar en la cookie. La respuesta incluye un nuevo `access_token`.

### 2.5. Cerrar sesión

**Endpoint**: `POST /auth/logout`

Invalida el refresh token actual (blacklist en Redis). También elimina la cookie.

---

## 3. Catálogo de Productos

### 3.1. Listar productos

**Endpoint**: `GET /products`

**Parámetros de consulta comunes**:

| Parámetro | Descripción | Ejemplo |
|-----------|-------------|---------|
| `q` | Búsqueda por texto | `?q=laptop` |
| `category` | Filtrar por categoría | `?category=electronics` |
| `min_price` / `max_price` | Rango de precios | `?min_price=100&max_price=500` |
| `cursor` | Paginación por cursor | `?cursor=...` |
| `limit` | Cantidad de resultados | `?limit=20` |

**Respuesta**:

```json
{
  "items": [...],
  "next_cursor": "eyJpZCI6IDEyM30=",
  "total": 450
}
```

### 3.2. Ver detalle de un producto

**Endpoint**: `GET /products/{id}`

### 3.3. Imágenes de productos

Las imágenes se almacenan en MinIO/S3. La URL pública de cada imagen viene incluida en el campo `image_url` del producto.

---

## 4. Carrito de Compras

El carrito funciona tanto para usuarios autenticados como para visitantes anónimos.

### 4.1. Carrito anónimo

Si el usuario no ha iniciado sesión, la API genera un `session_id` firmado y lo guarda en una cookie segura. El cliente no necesita hacer nada especial: las cookies se envían automáticamente.

### 4.2. Agregar producto al carrito

**Endpoint**: `POST /cart/items`

```json
{
  "product_id": 42,
  "quantity": 2
}
```

### 4.3. Ver carrito

**Endpoint**: `GET /cart`

**Respuesta**:

```json
{
  "items": [
    {
      "product_id": 42,
      "name": "Laptop Pro",
      "quantity": 2,
      "unit_price": 999.99,
      "subtotal": 1999.98
    }
  ],
  "total": 1999.98
}
```

### 4.4. Actualizar cantidad

**Endpoint**: `PATCH /cart/items/{product_id}`

```json
{
  "quantity": 3
}
```

### 4.5. Eliminar producto del carrito

**Endpoint**: `DELETE /cart/items/{product_id}`

### 4.6. Vaciar carrito

**Endpoint**: `DELETE /cart`

### 4.7. Migrar carrito anónimo al iniciar sesión

Cuando un usuario anónimo inicia sesión, el sistema puede fusionar automáticamente el carrito de la sesión con el carrito persistente del usuario (comportamiento configurable en el frontend).

---

## 5. Órdenes y Checkout

### 5.1. Crear una orden

**Endpoint**: `POST /orders` *(requiere autenticación y cuenta verificada)*

```json
{
  "shipping_address": {
    "street": "Av. Principal 123",
    "city": "Ciudad de México",
    "state": "CDMX",
    "zip_code": "01000",
    "country": "México"
  },
  "billing_address": {
    "street": "Av. Principal 123",
    "city": "Ciudad de México",
    "state": "CDMX",
    "zip_code": "01000",
    "country": "México"
  }
}
```

**Respuesta**: `201 Created` con los datos de la orden, incluyendo `id`, `total` y estado inicial `pending`.

### 5.2. Ver mis órdenes

**Endpoint**: `GET /orders`

### 5.3. Ver detalle de una orden

**Endpoint**: `GET /orders/{id}`

### 5.4. Estados de una orden

| Estado | Significado |
|--------|-------------|
| `pending` | Orden creada, esperando pago. |
| `paid` | Pago confirmado por Stripe. |
| `processing` | Preparando envío. |
| `shipped` | Enviada. |
| `delivered` | Entregada. |
| `cancelled` | Cancelada. |
| `refunded` | Reembolsada. |

---

## 6. Pagos con Stripe

### 6.1. Crear un PaymentIntent

**Endpoint**: `POST /payments/intent` *(requiere autenticación)*

```json
{
  "order_id": 123
}
```

**Respuesta**:

```json
{
  "client_secret": "pi_xxx_secret_yyy"
}
```

Usa `client_secret` en el frontend de Stripe (Stripe.js o SDK móvil) para confirmar el pago de forma segura.

### 6.2. Webhook de Stripe

El webhook es gestionado por el backend. No requiere acción del frontend, salvo redirigir al usuario a la página de confirmación una vez que Stripe confirme el pago.

### 6.3. Reembolsos

Solo administradores/staff pueden crear reembolsos desde el panel de administración.

---

## 7. Perfil de Usuario

### 7.1. Ver perfil

**Endpoint**: `GET /users/me`

### 7.2. Actualizar perfil

**Endpoint**: `PATCH /users/me`

```json
{
  "full_name": "Juan Pérez López",
  "phone": "+525555555555"
}
```

### 7.3. Cambiar contraseña

**Endpoint**: `POST /users/me/change-password`

```json
{
  "current_password": "...",
  "new_password": "..."
}
```

### 7.4. Recuperar contraseña

1. Solicitar email de recuperación: `POST /auth/password-reset-request`
2. Enviar nueva contraseña con el token recibido: `POST /auth/password-reset`

---

## 8. Administración

Endpoints bajo `/admin` requieren rol `admin` o `staff`:

- `GET /admin/users`: listar usuarios.
- `PATCH /admin/users/{id}/role`: cambiar rol.
- `POST /admin/products`: crear producto.
- `PATCH /admin/products/{id}`: editar producto.
- `DELETE /admin/products/{id}`: eliminar producto.
- `PATCH /admin/orders/{id}/status`: actualizar estado de orden.
- `POST /admin/refunds`: procesar reembolso.

---

## 9. Manejo de Errores Comunes

| Código | Significado | Qué hacer |
|--------|-------------|-----------|
| `400` | Solicitud incorrecta | Revisar el formato y valores enviados. |
| `401` | No autenticado | Iniciar sesión o refrescar el access token. |
| `403` | Sin permisos | El usuario no tiene acceso al recurso. |
| `404` | No encontrado | Verificar el ID del recurso. |
| `409` | Conflicto | Puede indicar email duplicado o stock insuficiente. |
| `422` | Error de validación | Revisar mensajes de Pydantic en `detail`. |
| `429` | Demasiadas solicitudes | Esperar antes de reintentar (rate limit). |
| `500` | Error interno | Contactar soporte o revisar logs. |

### Ejemplo de error de validación

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## 10. Buenas Prácticas para Consumidores de la API

1. **Almacena tokens de forma segura**: el `access_token` puede guardarse en memoria; el `refresh_token` ya está en cookie `HttpOnly`.
2. **Refresca el access token antes de expirar**: el token dura 15 minutos.
3. **Maneja el carrito anónimo**: permite agregar productos antes de registrarse.
4. **Verifica el email antes del checkout**: el backend bloquea órdenes si la cuenta no está verificada.
5. **Usa Stripe.js en el frontend**: nunca envíes datos de tarjeta al backend; usa el `client_secret`.
6. **Reutiliza conexiones HTTP/2** cuando sea posible para mejorar rendimiento.
7. **Lee `next_cursor` correctamente**: no uses `page` numérico en el catálogo.

---

## 11. Escenarios de Uso Típicos

### Escenario 1: Compra como usuario registrado

1. `POST /auth/register`
2. Verificar email con el token recibido.
3. `POST /auth/login`
4. `GET /products?q=laptop`
5. `POST /cart/items` con el producto elegido.
6. `POST /orders` con direcciones de envío y facturación.
7. `POST /payments/intent` para obtener `client_secret`.
8. Confirmar pago con Stripe.js.
9. Recibir email de confirmación.
10. `GET /orders/{id}` para ver estado.

### Escenario 2: Compra como visitante que luego inicia sesión

1. `GET /products` (sin autenticar).
2. `POST /cart/items` → se crea sesión anónima.
3. El usuario decide registrarse: `POST /auth/register`.
4. Al iniciar sesión, el carrito anónimo se puede fusionar.
5. Continuar con checkout y pago.

---

## 12. Preguntas Frecuentes

**¿Puedo usar la API sin autenticación?**
Solo para ver el catálogo. Para comprar, crear órdenes y pagar se requiere autenticación.

**¿Por qué mi orden falla con "stock insuficiente"?**
Otro usuario pudo comprar el último artículo. El stock se reserva al crear la orden.

**¿Cuánto dura el carrito anónimo?**
Depende de la expiración de la cookie de sesión, configurable en el backend.

**¿Cómo sé si un pago fue exitoso?**
Consulta el estado de la orden (`GET /orders/{id}`). El webhook de Stripe actualiza el estado a `paid`.

**¿Puedo cancelar una orden?**
Depende del estado. Las órdenes `pending` o `paid` pueden cancelarse según las reglas de negocio.
