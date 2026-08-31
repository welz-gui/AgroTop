import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}


val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    namespace = "com.agrotop.agrotop_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.agrotop.agrotop_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }


    signingConfigs {
        if (keystorePropertiesFile.exists()) {
            create("release") {
                keyAlias = keystoreProperties["keyAlias"] as String?
                    ?: error("keyAlias ausente em key.properties")
                keyPassword = keystoreProperties["keyPassword"] as String?
                    ?: error("keyPassword ausente em key.properties")
                // Relativo a android/app/ — se o .jks estiver em android/, use "../nome.jks".
                storeFile = file(
                    keystoreProperties["storeFile"] as String?
                        ?: error("storeFile ausente em key.properties")
                )
                storePassword = keystoreProperties["storePassword"] as String?
                    ?: error("storePassword ausente em key.properties")
            }
        }
    }

    buildTypes {
        release {
            // Nunca cai para a chave de debug silenciosamente: um release assinado com
            // debug e enviado à Play Store amarra essa chave como identidade permanente
            // do app, sem possibilidade de troca depois. Falha alto e cedo em vez disso.
            signingConfig = if (keystorePropertiesFile.exists()) {
                signingConfigs.getByName("release")
            } else {
                throw GradleException(
                    "Build de release sem android/key.properties — a assinatura de debug " +
                        "nunca deve gerar um release real (ficaria permanentemente amarrada " +
                        "como identidade do app na Play Store). Crie android/key.properties " +
                        "com storePassword/keyPassword/keyAlias/storeFile (caminho relativo " +
                        "a android/app/), ou rode 'flutter build apk --debug' para um build " +
                        "de teste."
                )
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
