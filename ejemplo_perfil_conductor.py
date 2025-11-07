#!/usr/bin/env python3
"""
Ejemplo de uso del sistema de perfil del conductor de TinCar
Este script muestra cómo utilizar todas las funciones del perfil
"""

import sys
import os

# Agregar el directorio TinCar al path para importar models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'TinCar'))

from models import (
    get_driver_profile,
    update_driver_profile,
    update_driver_verification_status,
    update_driver_stats,
    update_last_activity,
    check_license_validity,
    get_driver_age
)

def ejemplo_1_obtener_perfil():
    """Ejemplo 1: Obtener el perfil completo de un conductor"""
    print("=" * 60)
    print("EJEMPLO 1: Obtener perfil completo del conductor")
    print("=" * 60)
    
    user_id = 6  # juan2@gmail.com
    profile = get_driver_profile(user_id)
    
    if profile:
        print(f"\n✅ Perfil encontrado para usuario ID: {user_id}")
        print(f"📧 Nombre: {profile['name']}")
        print(f"📧 Email: {profile['email']}")
        print(f"📞 Teléfono: {profile['phone']}")
        print(f"⭐ Calificación: {profile['rating']}/5.0")
        print(f"📊 Reservaciones completadas: {profile['total_reservations']}")
        print(f"📊 Cancelaciones: {profile['total_cancellations']}")
        print(f"🔰 Estado de cuenta: {profile['account_status']}")
        print(f"✅ Documento verificado: {profile['document_verified']}")
        print(f"✅ Licencia verificada: {profile['license_verified']}")
    else:
        print(f"\n❌ No se encontró el perfil del usuario ID: {user_id}")
    
    print("\n")


def ejemplo_2_actualizar_perfil():
    """Ejemplo 2: Actualizar datos personales del conductor"""
    print("=" * 60)
    print("EJEMPLO 2: Actualizar datos personales del conductor")
    print("=" * 60)
    
    user_id = 6
    
    # Datos a actualizar
    datos_personales = {
        'document_type': 'Cédula de ciudadanía',
        'document_number': '1012345678',
        'birth_date': '1995-03-15',
        'address': 'Calle 100 #15-30, Apartamento 501, Bogotá',
        'gender': 'Masculino',
        'emergency_phone': '3001234567',
        'emergency_contact_name': 'María Pérez',
        'emergency_contact_relationship': 'Madre'
    }
    
    success = update_driver_profile(user_id, datos_personales)
    
    if success:
        print("\n✅ Datos personales actualizados correctamente")
        print(f"   📄 Documento: {datos_personales['document_type']} - {datos_personales['document_number']}")
        print(f"   🎂 Fecha de nacimiento: {datos_personales['birth_date']}")
        print(f"   🏠 Dirección: {datos_personales['address']}")
        print(f"   🚨 Contacto emergencia: {datos_personales['emergency_contact_name']} ({datos_personales['emergency_contact_relationship']})")
    else:
        print("\n❌ Error al actualizar datos personales")
    
    print("\n")


def ejemplo_3_actualizar_licencia():
    """Ejemplo 3: Actualizar información de licencia de conducción"""
    print("=" * 60)
    print("EJEMPLO 3: Actualizar información de licencia")
    print("=" * 60)
    
    user_id = 6
    
    # Datos de la licencia
    datos_licencia = {
        'license_number': 'BOG123456789',
        'license_expiry_date': '2028-12-31',
        'license_category': 'B1'
    }
    
    success = update_driver_profile(user_id, datos_licencia)
    
    if success:
        print("\n✅ Información de licencia actualizada")
        print(f"   🪪 Número: {datos_licencia['license_number']}")
        print(f"   📅 Vencimiento: {datos_licencia['license_expiry_date']}")
        print(f"   🚗 Categoría: {datos_licencia['license_category']}")
        
        # Verificar validez de la licencia
        validity = check_license_validity(user_id)
        if validity['valid']:
            print(f"   ✅ Licencia vigente - Vence en {validity['days_until_expiry']} días")
        else:
            print(f"   ❌ Licencia vencida")
    else:
        print("\n❌ Error al actualizar licencia")
    
    print("\n")


def ejemplo_4_actualizar_vehiculo():
    """Ejemplo 4: Registrar información del vehículo"""
    print("=" * 60)
    print("EJEMPLO 4: Registrar información del vehículo")
    print("=" * 60)
    
    user_id = 6
    
    # Datos del vehículo
    datos_vehiculo = {
        'vehicle_plate': 'ABC123',
        'vehicle_brand': 'Toyota',
        'vehicle_model': 'Corolla',
        'vehicle_color': 'Gris',
        'vehicle_year': 2020
    }
    
    success = update_driver_profile(user_id, datos_vehiculo)
    
    if success:
        print("\n✅ Información del vehículo registrada")
        print(f"   🚗 Vehículo: {datos_vehiculo['vehicle_brand']} {datos_vehiculo['vehicle_model']}")
        print(f"   🔖 Placa: {datos_vehiculo['vehicle_plate']}")
        print(f"   🎨 Color: {datos_vehiculo['vehicle_color']}")
        print(f"   📅 Año: {datos_vehiculo['vehicle_year']}")
    else:
        print("\n❌ Error al registrar vehículo")
    
    print("\n")


def ejemplo_5_verificar_documentos():
    """Ejemplo 5: Verificar documentos del conductor"""
    print("=" * 60)
    print("EJEMPLO 5: Verificar documentos (Admin)")
    print("=" * 60)
    
    user_id = 6
    
    # Verificar documento de identidad
    success1 = update_driver_verification_status(user_id, document_verified='verificado')
    
    # Verificar licencia de conducción
    success2 = update_driver_verification_status(user_id, license_verified='verificado')
    
    if success1 and success2:
        print("\n✅ Documentos verificados correctamente")
        print("   ✅ Documento de identidad: VERIFICADO")
        print("   ✅ Licencia de conducción: VERIFICADA")
    else:
        print("\n❌ Error al verificar documentos")
    
    print("\n")


def ejemplo_6_actualizar_estadisticas():
    """Ejemplo 6: Actualizar estadísticas del conductor"""
    print("=" * 60)
    print("EJEMPLO 6: Actualizar estadísticas del conductor")
    print("=" * 60)
    
    user_id = 6
    
    # Incrementar reservaciones completadas
    success1 = update_driver_stats(user_id, increment_reservations=True)
    
    # Actualizar calificación
    success2 = update_driver_stats(user_id, rating=4.8)
    
    if success1 and success2:
        print("\n✅ Estadísticas actualizadas")
        print("   📈 Reservaciones completadas: +1")
        print("   ⭐ Nueva calificación: 4.8/5.0")
    else:
        print("\n❌ Error al actualizar estadísticas")
    
    print("\n")


def ejemplo_7_verificar_edad():
    """Ejemplo 7: Verificar edad del conductor"""
    print("=" * 60)
    print("EJEMPLO 7: Verificar edad del conductor")
    print("=" * 60)
    
    user_id = 6
    
    age = get_driver_age(user_id)
    
    if age is not None:
        print(f"\n✅ Edad calculada: {age} años")
        if age >= 18:
            print("   ✅ Cumple con edad mínima para conducir")
        else:
            print("   ❌ NO cumple con edad mínima para conducir")
    else:
        print("\n⚠️ No se ha registrado fecha de nacimiento")
    
    print("\n")


def ejemplo_8_verificar_licencia_vencimiento():
    """Ejemplo 8: Verificar vencimiento de licencia"""
    print("=" * 60)
    print("EJEMPLO 8: Verificar vencimiento de licencia")
    print("=" * 60)
    
    user_id = 6
    
    validity = check_license_validity(user_id)
    
    if validity['expiry_date']:
        print(f"\n📅 Fecha de vencimiento: {validity['expiry_date']}")
        
        if validity['valid']:
            days = validity['days_until_expiry']
            print(f"✅ Licencia vigente")
            print(f"   Días restantes: {days}")
            
            if days < 30:
                print(f"   ⚠️ ALERTA: La licencia vence pronto!")
            elif days < 90:
                print(f"   ⚠️ Recordatorio: Considera renovar tu licencia")
        else:
            print("❌ LICENCIA VENCIDA")
            print("   ⚠️ Debes renovar tu licencia antes de realizar reservaciones")
    else:
        print("\n⚠️ No se ha registrado información de licencia")
    
    print("\n")


def ejemplo_9_perfil_completo():
    """Ejemplo 9: Llenar perfil completo de un conductor nuevo"""
    print("=" * 60)
    print("EJEMPLO 9: Llenar perfil completo de conductor nuevo")
    print("=" * 60)
    
    user_id = 7  # juan3@gmail.com
    
    # Datos completos del conductor
    perfil_completo = {
        # Información personal
        'name': 'Juan Pérez Gómez',
        'phone': '3209876543',
        'document_type': 'Cédula de ciudadanía',
        'document_number': '1098765432',
        'birth_date': '1998-07-20',
        'gender': 'Masculino',
        'address': 'Carrera 7 #100-50, Bogotá',
        
        # Contacto de emergencia
        'emergency_phone': '3101234567',
        'emergency_contact_name': 'Ana Gómez',
        'emergency_contact_relationship': 'Hermana',
        
        # Licencia de conducción
        'license_number': 'BOG987654321',
        'license_expiry_date': '2029-06-15',
        'license_category': 'B1',
        
        # Vehículo
        'vehicle_plate': 'XYZ789',
        'vehicle_brand': 'Mazda',
        'vehicle_model': 'CX-5',
        'vehicle_color': 'Azul',
        'vehicle_year': 2021
    }
    
    success = update_driver_profile(user_id, perfil_completo)
    
    if success:
        print("\n✅ Perfil completo creado exitosamente")
        print("\n📋 INFORMACIÓN PERSONAL:")
        print(f"   Nombre: {perfil_completo['name']}")
        print(f"   Documento: {perfil_completo['document_type']} - {perfil_completo['document_number']}")
        print(f"   Fecha nacimiento: {perfil_completo['birth_date']}")
        print(f"   Dirección: {perfil_completo['address']}")
        
        print("\n🚨 CONTACTO DE EMERGENCIA:")
        print(f"   Nombre: {perfil_completo['emergency_contact_name']}")
        print(f"   Relación: {perfil_completo['emergency_contact_relationship']}")
        print(f"   Teléfono: {perfil_completo['emergency_phone']}")
        
        print("\n🪪 LICENCIA DE CONDUCCIÓN:")
        print(f"   Número: {perfil_completo['license_number']}")
        print(f"   Categoría: {perfil_completo['license_category']}")
        print(f"   Vencimiento: {perfil_completo['license_expiry_date']}")
        
        print("\n🚗 VEHÍCULO:")
        print(f"   {perfil_completo['vehicle_brand']} {perfil_completo['vehicle_model']} ({perfil_completo['vehicle_year']})")
        print(f"   Placa: {perfil_completo['vehicle_plate']}")
        print(f"   Color: {perfil_completo['vehicle_color']}")
    else:
        print("\n❌ Error al crear perfil completo")
    
    print("\n")


def main():
    """Función principal que ejecuta todos los ejemplos"""
    print("\n")
    print("🚗" * 30)
    print(" " * 15 + "SISTEMA DE PERFIL DEL CONDUCTOR - TINCAR")
    print("🚗" * 30)
    print("\n")
    
    # Ejecutar todos los ejemplos
    ejemplo_1_obtener_perfil()
    ejemplo_2_actualizar_perfil()
    ejemplo_3_actualizar_licencia()
    ejemplo_4_actualizar_vehiculo()
    ejemplo_5_verificar_documentos()
    ejemplo_6_actualizar_estadisticas()
    ejemplo_7_verificar_edad()
    ejemplo_8_verificar_licencia_vencimiento()
    ejemplo_9_perfil_completo()
    
    print("=" * 60)
    print("✅ TODOS LOS EJEMPLOS COMPLETADOS")
    print("=" * 60)
    print("\n")


if __name__ == "__main__":
    main()
