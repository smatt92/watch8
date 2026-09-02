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
        // The official samples set isMinifyEnabled = true on both build types,
        // but this package has hasCode="false" and no sources, so R8 has no
        // classes to process. Leaving it on only adds a minify task and makes
        // AGP warn that debug is both debuggable and minified.
        debug {
            isMinifyEnabled = false
        }
        release {
            // TODO: Add your signingConfig here to build release builds.
            isMinifyEnabled = false
            // Must stay false, otherwise watch face resources can be stripped.
            // (AGP also requires minify for shrinking, so this is belt and braces.)
            isShrinkResources = false

            signingConfig = signingConfigs.getByName("debug")
        }
    }
}
