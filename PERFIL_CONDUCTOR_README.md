# 📋 SISTEMA DE PERFIL DEL CONDUCTOR - TINCAR

## 🎯 Resumen
Se ha implementado un sistema completo de perfil para conductores en TinCar, con 27 campos adicionales en la base de datos y 8 funciones especializadas para gestionar toda la información del conductor.

---

## 📊 CAMPOS DE LA BASE DE DATOS

### 1️⃣ INFORMACIÓN PERSONAL BÁSICA (Ya existentes)
- ✅ **id** - ID único del usuario
- ✅ **name** - Nombre completo
- ✅ **email** - Correo electrónico (único)
- ✅ **password** - Contraseña encriptada
- ✅ **phone** - Teléfono principal
- ✅ **role** - Rol del usuario (conductor/arrendador)

### 2️⃣ DOCUMENTACIÓN DE IDENTIDAD
- 🆕 **document_type** - Tipo de documento
  - Opciones: "Cédula de ciudadanía" / "Cédula extranjera" / "Pasaporte"
- 🆕 **document_number** - Número del documento
- 🆕 **document_photo** - Ruta a la foto del documento
- 🆕 **document_verified** - Estado de verificación
  - Valores: "pendiente" (default) / "verificado" / "rechazado"

### 3️⃣ INFORMACIÓN DE CONTACTO
- 🆕 **emergency_phone** - Teléfono en caso de emergencia
- 🆕 **emergency_contact_name** - Nombre del contacto de emergencia
- 🆕 **emergency_contact_relationship** - Relación con el contacto de emergencia
  - Ejemplos: "Padre", "Madre", "Hermano/a", "Cónyuge", "Amigo/a"

### 4️⃣ DATOS PERSONALES
- 🆕 **birth_date** - Fecha de nacimiento (formato: YYYY-MM-DD)
  - Usado para verificar edad legal para conducir (≥18 años)
- 🆕 **address** - Dirección completa del domicilio
- 🆕 **gender** - Género (opcional)
  - Opciones: "Masculino" / "Femenino" / "Otro" / "Prefiero no decir"
- 🆕 **profile_photo** - Ruta a la foto de perfil

### 5️⃣ LICENCIA DE CONDUCCIÓN
- 🆕 **license_number** - Número de licencia de conducción
- 🆕 **license_expiry_date** - Fecha de vencimiento (formato: YYYY-MM-DD)
- 🆕 **license_category** - Categoría de la licencia
  - Categorías Colombia: A1, A2, B1, B2, B3, C1, C2, C3
  - A1: Motocicletas hasta 125cc
  - A2: Motocicletas superiores a 125cc
  - B1: Automóviles, camperos, camionetas
  - B2: Vehículos B1 + remolque
  - B3: Vehículos de servicio público (taxis, buses pequeños)
  - C1: Camiones rígidos
  - C2: Camiones articulados
  - C3: Vehículos articulados pesados
- 🆕 **license_photo** - Ruta a la foto de la licencia
- 🆕 **license_verified** - Estado de verificación
  - Valores: "pendiente" (default) / "verificado" / "rechazado"

### 6️⃣ INFORMACIÓN DEL VEHÍCULO (Opcional)
- 🆕 **vehicle_plate** - Placa del vehículo principal
- 🆕 **vehicle_brand** - Marca del vehículo
  - Ejemplos: "Toyota", "Chevrolet", "Mazda", "Renault"
- 🆕 **vehicle_model** - Modelo del vehículo
  - Ejemplos: "Corolla", "Spark", "CX-5", "Logan"
- 🆕 **vehicle_color** - Color del vehículo
- 🆕 **vehicle_year** - Año del vehículo (INTEGER)

### 7️⃣ ESTADÍSTICAS Y CALIDAD DE SERVICIO
- 🆕 **rating** - Calificación promedio (REAL, default: 0.0)
  - Rango: 0.0 a 5.0
- 🆕 **total_reservations** - Total de reservaciones completadas (INTEGER, default: 0)
- 🆕 **total_cancellations** - Número de cancelaciones (INTEGER, default: 0)
- 🆕 **account_status** - Estado de la cuenta
  - Valores: "activo" (default) / "suspendido" / "bloqueado"

### 8️⃣ AUDITORÍA Y CONTROL
- ✅ **created_at** - Fecha de registro (TIMESTAMP, ya existente)
- 🆕 **last_activity** - Última actividad del usuario (TIMESTAMP)

---

## 🛠️ FUNCIONES DISPONIBLES

### 1. `get_driver_profile(user_id)`
Obtiene el perfil completo del conductor con todos sus datos.

**Parámetros:**
- `user_id` (int): ID del usuario

**Retorna:**
- `dict`: Diccionario con todos los campos del perfil
- `None`: Si el usuario no existe

**Ejemplo de uso:**
```python
from models import get_driver_profile

profile = get_driver_profile(6)
if profile:
    print(f"Conductor: {profile['name']}")
    print(f"Licencia: {profile['license_number']}")
    print(f"Calificación: {profile['rating']}/5.0")
```

---

### 2. `update_driver_profile(user_id, profile_data)`
Actualiza la información del perfil del conductor.

**Parámetros:**
- `user_id` (int): ID del usuario
- `profile_data` (dict): Diccionario con los campos a actualizar

**Campos permitidos:**
- name, phone, document_type, document_number
- emergency_phone, emergency_contact_name, emergency_contact_relationship
- birth_date, address, profile_photo, document_photo
- license_number, license_expiry_date, license_category, license_photo
- gender, vehicle_plate, vehicle_brand, vehicle_model, vehicle_color, vehicle_year

**Retorna:**
- `bool`: True si la actualización fue exitosa

**Ejemplo de uso:**
```python
from models import update_driver_profile

datos = {
    'document_type': 'Cédula de ciudadanía',
    'document_number': '1234567890',
    'birth_date': '1995-03-15',
    'address': 'Calle 123 #45-67, Bogotá',
    'license_number': 'ABC123456789',
    'license_expiry_date': '2028-12-31',
    'license_category': 'B1',
    'vehicle_plate': 'ABC123',
    'vehicle_brand': 'Toyota',
    'vehicle_model': 'Corolla',
    'vehicle_year': 2020,
    'emergency_phone': '3001234567',
    'emergency_contact_name': 'María Pérez',
    'emergency_contact_relationship': 'Madre'
}

success = update_driver_profile(6, datos)
```

---

### 3. `update_driver_verification_status(user_id, document_verified, license_verified)`
Actualiza el estado de verificación de documentos y/o licencia.

**Parámetros:**
- `user_id` (int): ID del usuario
- `document_verified` (str, opcional): "pendiente" / "verificado" / "rechazado"
- `license_verified` (str, opcional): "pendiente" / "verificado" / "rechazado"

**Retorna:**
- `bool`: True si la actualización fue exitosa

**Ejemplo de uso:**
```python
from models import update_driver_verification_status

# Verificar documento
update_driver_verification_status(6, document_verified='verificado')

# Verificar licencia
update_driver_verification_status(6, license_verified='verificado')

# Verificar ambos
update_driver_verification_status(6, 
    document_verified='verificado', 
    license_verified='verificado'
)
```

---

### 4. `update_driver_stats(user_id, rating, increment_reservations, increment_cancellations)`
Actualiza las estadísticas del conductor.

**Parámetros:**
- `user_id` (int): ID del usuario
- `rating` (float, opcional): Nueva calificación promedio (0.0 - 5.0)
- `increment_reservations` (bool, opcional): Incrementar contador de reservaciones
- `increment_cancellations` (bool, opcional): Incrementar contador de cancelaciones

**Retorna:**
- `bool`: True si la actualización fue exitosa

**Ejemplo de uso:**
```python
from models import update_driver_stats

# Actualizar calificación
update_driver_stats(6, rating=4.8)

# Incrementar reservaciones completadas
update_driver_stats(6, increment_reservations=True)

# Incrementar cancelaciones
update_driver_stats(6, increment_cancellations=True)
```

---

### 5. `update_last_activity(user_id)`
Actualiza la última actividad del usuario al momento actual.

**Parámetros:**
- `user_id` (int): ID del usuario

**Ejemplo de uso:**
```python
from models import update_last_activity

# Llamar cada vez que el usuario haga alguna acción
update_last_activity(6)
```

---

### 6. `check_license_validity(user_id)`
Verifica si la licencia de conducción está vigente.

**Parámetros:**
- `user_id` (int): ID del usuario

**Retorna:**
- `dict`: {
    - 'valid': bool - Si la licencia está vigente
    - 'days_until_expiry': int - Días hasta el vencimiento
    - 'expiry_date': str - Fecha de vencimiento (YYYY-MM-DD)
  }

**Ejemplo de uso:**
```python
from models import check_license_validity

validity = check_license_validity(6)
if validity['valid']:
    days = validity['days_until_expiry']
    if days < 30:
        print(f"⚠️ Tu licencia vence en {days} días")
else:
    print("❌ Licencia vencida")
```

---

### 7. `get_driver_age(user_id)`
Calcula la edad actual del conductor basado en su fecha de nacimiento.

**Parámetros:**
- `user_id` (int): ID del usuario

**Retorna:**
- `int`: Edad del conductor
- `None`: Si no tiene fecha de nacimiento registrada

**Ejemplo de uso:**
```python
from models import get_driver_age

age = get_driver_age(6)
if age:
    if age < 18:
        print("❌ No cumple edad mínima para conducir")
    else:
        print(f"✅ Conductor de {age} años")
```

---

## 💡 DATOS ADICIONALES RECOMENDADOS (Futura implementación)

### 🔒 Seguridad y Verificación Adicional
1. **Verificación biométrica**
   - Foto de selfie para verificar identidad
   - Comparación facial con documento

2. **Antecedentes**
   - Certificado de antecedentes penales
   - Certificado de comparendos de tránsito

### 📱 Preferencias y Configuración
3. **Preferencias de notificaciones**
   - Email / SMS / Push notifications
   - Frecuencia de notificaciones

4. **Preferencias de uso**
   - Zona preferida de búsqueda
   - Radio máximo de búsqueda (km)
   - Precio máximo dispuesto a pagar

### 💳 Información de Pago
5. **Métodos de pago**
   - Tarjeta de crédito/débito
   - PSE
   - Billetera digital

### 🏆 Gamificación y Fidelización
6. **Programa de puntos**
   - Puntos acumulados
   - Nivel del conductor (Bronce, Plata, Oro, Platino)
   - Insignias ganadas

### 📊 Análisis y Estadísticas
7. **Estadísticas de uso**
   - Tiempo promedio de estacionamiento
   - Horarios preferidos de uso
   - Gastos totales en la plataforma
   - CO2 ahorrado (vs buscar parqueadero)

### 🚗 Vehículos adicionales
8. **Múltiples vehículos**
   - Tabla separada para vehículos
   - Cada vehículo con SOAT, revisión técnico-mecánica
   - Seguro obligatorio

---

## 🎨 PRÓXIMOS PASOS SUGERIDOS

### 1. **Crear interfaz de usuario para el perfil**
   - Formulario de edición de perfil
   - Carga de imágenes (documento, licencia, foto de perfil)
   - Visualización de estadísticas

### 2. **Sistema de verificación**
   - Panel de administrador para verificar documentos
   - Notificaciones de verificación aprobada/rechazada
   - Restricciones si no está verificado

### 3. **Validaciones**
   - Edad mínima (18 años)
   - Licencia vigente antes de crear reservaciones
   - Formato de documentos (regex)
   - Tamaño y formato de imágenes

### 4. **APIs REST**
   - GET /api/driver/profile/:id
   - PUT /api/driver/profile/:id
   - POST /api/driver/profile/upload-photo
   - GET /api/driver/stats/:id

### 5. **Sistema de calificaciones**
   - Los arrendadores califican a los conductores
   - Comentarios y reseñas
   - Promedio ponderado de calificaciones

---

## 📝 NOTAS TÉCNICAS

- Todos los campos nuevos son **opcionales** (NULL permitido)
- Los valores por defecto ya están configurados en la BD
- Las funciones usan transacciones para garantizar integridad
- El campo `updated_at` se actualiza automáticamente en cada modificación
- Las fechas usan formato ISO 8601 (YYYY-MM-DD)
- Las rutas de imágenes deben almacenar paths relativos a `/static/uploads/`

---

## ✅ ESTADO ACTUAL

- ✅ Base de datos actualizada (27 nuevas columnas)
- ✅ 8 funciones de gestión implementadas
- ✅ Valores por defecto configurados
- ✅ Sistema de verificación de documentos
- ✅ Validación de licencia
- ✅ Cálculo de edad
- ⏳ Pendiente: Interfaces de usuario
- ⏳ Pendiente: APIs REST
- ⏳ Pendiente: Sistema de carga de imágenes
- ⏳ Pendiente: Panel de administración

---

**Fecha de implementación:** 7 de Noviembre de 2025  
**Archivo de modelos:** `/workspaces/Tincar/TinCar/models.py`  
**Base de datos:** `/workspaces/Tincar/TinCar/database/tincar.db`
