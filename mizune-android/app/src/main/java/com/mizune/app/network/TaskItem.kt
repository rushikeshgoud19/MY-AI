package com.mizune.app.network

import kotlinx.serialization.Serializable

@Serializable
data class TaskItem(
    val id: String = "",
    val description: String = "",
    val status: String = "pending"
)
