plugins {
    alias(libs.plugins.android.application)
}

android {
    // Watch Face Format packages are resource-only: no Java/Kotlin sources.
    enableKotlin = false
    namespace = "com.watch8.minimalanalog"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.watch8.minimalanalog"
        // WFF v4 requires Wear OS 6 / API 36. Matches the PhotosMask v4 sample.
        minSdk = 36
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
