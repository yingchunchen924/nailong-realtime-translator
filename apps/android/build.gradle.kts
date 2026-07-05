plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val nailongCompileSdk = providers.gradleProperty("nailong.compileSdk").orNull?.toInt() ?: 35
val nailongTargetSdk = providers.gradleProperty("nailong.targetSdk").orNull?.toInt() ?: nailongCompileSdk
val nailongBuildTools = providers.gradleProperty("nailong.buildTools").orNull

android {
    namespace = "com.nailong.realtimetranslator"
    compileSdk = nailongCompileSdk
    nailongBuildTools?.let {
        buildToolsVersion = it
    }

    defaultConfig {
        applicationId = "com.nailong.realtimetranslator"
        minSdk = 29
        targetSdk = nailongTargetSdk
        versionCode = 7
        versionName = "0.1.7"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation("com.google.mlkit:text-recognition:16.0.1")
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
    implementation("com.google.mlkit:text-recognition-japanese:16.0.1")
    implementation("com.google.mlkit:text-recognition-korean:16.0.1")
    implementation("com.google.mlkit:language-id:17.0.6")
    implementation("com.google.mlkit:translate:17.0.3")
}
