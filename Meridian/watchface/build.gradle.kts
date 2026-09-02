plugins {
    alias(libs.plugins.android.application)
}

android {
    // Watch Face Format packages are resource-only: no Java/Kotlin sources.
    enableKotlin = false
    namespace = "com.watch8.meridian"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.watch8.meridian"
        // WFF v2 requires Wear OS 5 / API 34. Matches the Complications/Weather/Flavors v2 samples.
        minSdk = 34
        targetSdk = 37
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        debug {
            isMinifyEnabled = true
        }
        release {
            // TODO: Add your signingConfig here to build release builds.
            isMinifyEnabled = true
            // Must stay false, otherwise watch face resources can be stripped.
            isShrinkResources = false

            signingConfig = signingConfigs.getByName("debug")
        }
    }
}
